"""Limite de tentativas de login.

Sem isto, `/auth/login` aceita tentativas infinitas: dá para varrer senha por
força bruta contra uma conta conhecida sem que nada no sistema reaja. As
contas do studio são cinco e as senhas foram escolhidas por pessoas, então o
espaço de busca é pequeno — é o tipo de porta que se fecha antes de publicar,
não depois.

## Por que duas contagens, e não uma por IP

O studio inteiro sai pelo mesmo IP: recepção, proprietária e instrutores
dividem o roteador da sala. Bloquear só por IP significa que a recepcionista
errar a senha cinco vezes numa segunda de manhã derruba o login de todo
mundo, no horário de pico. Isso é dano operacional real, causado por nós.

Então a contagem principal é **por conta**: quem está sob ataque é o e-mail
alvo, e é ele que trava. A contagem por IP existe em segundo plano, com
limite bem mais folgado, para pegar o caso que a contagem por conta não vê —
varrer muitos e-mails diferentes com uma senha provável cada.

## Por que em memória, e não Redis

A API roda como uma instância só no plano gratuito do Render. Redis seria
mais infraestrutura para operar, provisionar e explicar na banca, para
resolver um problema que este projeto não tem. A troca é consciente e tem
consequência conhecida: **o contador é por processo**. Subindo com mais de um
worker, o limite efetivo multiplica pelo número de workers, e um restart
zera tudo. Para o porte do studio, aceitável; para escalar, o lugar de trocar
é só este arquivo — a API pública (`registrar_falha`, `verificar`,
`registrar_sucesso`) não mudaria.

## Privacidade

`app/core/logs.py` proíbe e-mail no log. A conta bloqueada é registrada como
um hash curto: quem tem o banco resolve quem é, quem só tem o log não. Ver a
regra em logs.py.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request

from app.core.config import get_settings
from app.core.logs import logger


def identificar_origem(request: Request) -> str:
    """IP de origem, considerando o proxy do Render.

    Em produção a app fica atrás do proxy da plataforma, então
    `request.client.host` é sempre o IP do proxy — todas as tentativas
    cairiam no mesmo balde. O primeiro endereço de `X-Forwarded-For` é o
    cliente real.

    Esse cabeçalho é falsificável por quem chama direto, o que derruba
    *apenas* a contagem por IP. A contagem por conta, que é a defesa
    principal, não depende dele.
    """
    encaminhado = request.headers.get("X-Forwarded-For")
    if encaminhado:
        primeiro = encaminhado.split(",")[0].strip()
        if primeiro:
            return primeiro
    return request.client.host if request.client else "desconhecido"


def _identificador_de_conta(email: str) -> str:
    """Hash curto e estável do e-mail, para contar sem guardar o e-mail."""
    normalizado = email.strip().lower().encode("utf-8")
    return hashlib.sha256(normalizado).hexdigest()[:12]


@dataclass(frozen=True)
class Bloqueio:
    """Resultado de uma verificação que barrou a tentativa."""

    segundos_restantes: int
    motivo: str


class _Contador:
    """Janela deslizante de falhas por chave.

    Guarda o instante de cada falha e descarta o que saiu da janela. Simples
    o bastante para caber na cabeça de quem for revisar, e o volume é de
    dezenas de eventos por dia — não vale estrutura mais esperta.
    """

    def __init__(self, maximo: int, janela_s: float, bloqueio_s: float) -> None:
        self.maximo = maximo
        self.janela_s = janela_s
        self.bloqueio_s = bloqueio_s
        self._falhas: defaultdict[str, deque[float]] = defaultdict(deque)

    def _podar(self, chave: str, agora: float) -> deque[float]:
        falhas = self._falhas[chave]
        while falhas and agora - falhas[0] > self.janela_s:
            falhas.popleft()
        return falhas

    def bloqueio(self, chave: str, agora: float) -> float:
        """Segundos restantes de bloqueio para a chave, ou 0."""
        falhas = self._podar(chave, agora)
        if len(falhas) < self.maximo:
            return 0.0
        # O relógio corre a partir da última falha CONTADA. Quem chama não
        # registra tentativa durante o bloqueio (ver o endpoint de login),
        # então o prazo não se estende sozinho: quem souber o e-mail da
        # recepção não consegue mantê-la trancada indefinidamente martelando
        # o login. O bloqueio é defesa, não arma.
        restante = self.bloqueio_s - (agora - falhas[-1])
        return max(restante, 0.0)

    def registrar(self, chave: str, agora: float) -> None:
        self._podar(chave, agora).append(agora)

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)

    def zerar(self) -> None:
        self._falhas.clear()


class LimitadorDeLogin:
    """Guarda as duas contagens e decide se a tentativa passa."""

    def __init__(self) -> None:
        s = get_settings()
        janela = s.LOGIN_JANELA_MINUTOS * 60
        bloqueio = s.LOGIN_BLOQUEIO_MINUTOS * 60
        self._lock = threading.Lock()
        self.por_conta = _Contador(s.LOGIN_MAX_TENTATIVAS_CONTA, janela, bloqueio)
        self.por_ip = _Contador(s.LOGIN_MAX_TENTATIVAS_IP, janela, bloqueio)

    def verificar(self, *, email: str, ip: str) -> Bloqueio | None:
        """Diz se a tentativa deve ser barrada antes de tocar no banco."""
        agora = time.monotonic()
        conta = _identificador_de_conta(email)
        with self._lock:
            restante_conta = self.por_conta.bloqueio(conta, agora)
            restante_ip = self.por_ip.bloqueio(ip, agora)

        if restante_conta > 0:
            return Bloqueio(int(restante_conta) + 1, "conta")
        if restante_ip > 0:
            return Bloqueio(int(restante_ip) + 1, "origem")
        return None

    def registrar_falha(self, *, email: str, ip: str) -> None:
        agora = time.monotonic()
        conta = _identificador_de_conta(email)
        with self._lock:
            self.por_conta.registrar(conta, agora)
            self.por_ip.registrar(ip, agora)

    def registrar_sucesso(self, *, email: str) -> None:
        """Login certo limpa a conta.

        Só a conta: se a origem acumulou falhas varrendo vários e-mails, um
        acerto isolado não deve apagar esse rastro.
        """
        with self._lock:
            self.por_conta.limpar(_identificador_de_conta(email))

    def zerar(self) -> None:
        """Descarta todo o estado. Usado entre testes."""
        with self._lock:
            self.por_conta.zerar()
            self.por_ip.zerar()


_limitador: LimitadorDeLogin | None = None


def obter_limitador() -> LimitadorDeLogin:
    """Instância única, criada na primeira chamada.

    Preguiçosa de propósito: `get_settings()` precisa do ambiente já montado,
    e no import do módulo isso ainda não é garantido na suíte de testes.
    """
    global _limitador
    if _limitador is None:
        _limitador = LimitadorDeLogin()
    return _limitador


def registrar_bloqueio_no_log(bloqueio: Bloqueio, *, email: str, ip: str) -> None:
    """Registra a recusa. Sem e-mail — ver o cabeçalho deste módulo."""
    logger.warning(
        "login bloqueado por excesso de tentativas",
        extra={
            "contexto": {
                "motivo": bloqueio.motivo,
                "conta_hash": _identificador_de_conta(email),
                "origem": ip,
                "segundos_restantes": bloqueio.segundos_restantes,
            }
        },
    )
