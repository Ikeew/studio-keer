"""Seed de demonstração: um studio fictício que conta uma história.

NÃO É DADO REAL. Nenhum CPF aqui pertence a alguém — todos falham nos
dígitos verificadores de propósito. Todos os telefones usam o prefixo
reservado 5550, que não existe no plano de numeração brasileiro.

O objetivo não é encher o banco. É montar um studio onde cada dor resolvida
pode ser demonstrada ao vivo:

  - uma turma COMPLETA, para a quinta matrícula ser recusada na frente da
    banca;
  - faltas justificadas com reposição pendente, algumas com prazo apertado,
    para o painel de reposições ter o que mostrar;
  - uma reposição já feita, mostrando o vínculo com a falta de origem;
  - mensalidades pagas, pendentes e vencidas, com vencimentos em dias
    diferentes — inclusive alguém que começou dia 31;
  - pacotes com saldos diferentes, um perto de vencer;
  - cancelamentos com motivo registrado.

TODAS as datas são relativas a hoje. O seed precisa continuar fazendo sentido
no dia da apresentação, seja quando for.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.sql import Delete

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.charge import Charge, FormaPagamento, StatusCobranca
from app.models.enrollment import Blackout, Enrollment, EnrollmentHorario
from app.models.package import Package
from app.models.patient import EstadoCivil, Patient, Sexo
from app.models.service import Service
from app.models.session import Session
from app.models.user import Papel, User
from app.services import booking_service, charge_service, enrollment_service
from app.services.schedule_service import FUSO

#: Marca todo registro criado por este comando. Serve para o `limpar` saber o
#: que remover sem tocar em dado digitado à mão durante a demonstração.
MARCA_DEMO = "[demo]"

# Telefones começam com 5550 — prefixo reservado, nenhum número real.
_PREFIXO_FICTICIO = "5550"


def _tel(seq: int) -> str:
    return f"119{_PREFIXO_FICTICIO}{seq:04d}"[:11]


def _cpf_invalido(seq: int) -> str:
    """CPF com dígitos verificadores propositalmente errados.

    Passa no formato e falha na validação — exatamente para que ninguém possa
    usar como documento, e para que a tela mostre o campo preenchido.
    """
    base = f"{seq:09d}"
    return base + "00"


@dataclass
class PacienteDemo:
    nome: str
    idade: int
    sexo: Sexo
    estado_civil: EstadoCivil
    profissao: str
    ativo: bool = True


# Nomes brasileiros plausíveis, idades variadas. Os quatro últimos estão
# inativos, para a busca com "incluir inativos" ter o que mostrar.
PACIENTES = [
    PacienteDemo("Maria Silva Andrade", 35, Sexo.FEMININO, EstadoCivil.CASADO, "Advogada"),
    PacienteDemo("João Pedro Santos", 42, Sexo.MASCULINO, EstadoCivil.CASADO, "Engenheiro"),
    PacienteDemo("Ana Beatriz Costa", 28, Sexo.FEMININO, EstadoCivil.SOLTEIRO, "Designer"),
    PacienteDemo("Carlos Eduardo Lima", 51, Sexo.MASCULINO, EstadoCivil.DIVORCIADO, "Contador"),
    PacienteDemo("Fernanda Oliveira", 33, Sexo.FEMININO, EstadoCivil.UNIAO_ESTAVEL, "Arquiteta"),
    PacienteDemo("Roberto Carvalho", 60, Sexo.MASCULINO, EstadoCivil.CASADO, "Aposentado"),
    PacienteDemo("Juliana Martins", 26, Sexo.FEMININO, EstadoCivil.SOLTEIRO, "Fisioterapeuta"),
    PacienteDemo("Paulo Henrique Rocha", 47, Sexo.MASCULINO, EstadoCivil.CASADO, "Dentista"),
    PacienteDemo("Camila Ferreira", 31, Sexo.FEMININO, EstadoCivil.SOLTEIRO, "Publicitária"),
    PacienteDemo("Ricardo Almeida", 38, Sexo.MASCULINO, EstadoCivil.CASADO, "Professor"),
    PacienteDemo("Patrícia Nunes", 45, Sexo.FEMININO, EstadoCivil.VIUVO, "Enfermeira"),
    PacienteDemo("Gustavo Barbosa", 22, Sexo.MASCULINO, EstadoCivil.SOLTEIRO, "Estudante"),
    PacienteDemo("Luciana Mendes", 55, Sexo.FEMININO, EstadoCivil.CASADO, "Empresária"),
    PacienteDemo("Thiago Ribeiro", 29, Sexo.MASCULINO, EstadoCivil.UNIAO_ESTAVEL, "Analista"),
    PacienteDemo("Sandra Dias Moreira", 63, Sexo.FEMININO, EstadoCivil.VIUVO, "Aposentada"),
    PacienteDemo("Bruno Almeida Souza", 36, Sexo.MASCULINO, EstadoCivil.SOLTEIRO, "Vendedor"),
    PacienteDemo("Adriana Mendes Pinto", 41, Sexo.FEMININO, EstadoCivil.CASADO, "Jornalista"),
    PacienteDemo(
        "Marcos Vinícius Teixeira", 34, Sexo.MASCULINO, EstadoCivil.SOLTEIRO, "Programador"
    ),
    # Inativos — desligados do studio, mas com histórico preservado.
    PacienteDemo(
        "Renata Lopes", 39, Sexo.FEMININO, EstadoCivil.DIVORCIADO, "Psicóloga", ativo=False
    ),
    PacienteDemo(
        "Felipe Cardoso", 44, Sexo.MASCULINO, EstadoCivil.CASADO, "Farmacêutico", ativo=False
    ),
    PacienteDemo(
        "Beatriz Tavares", 27, Sexo.FEMININO, EstadoCivil.SOLTEIRO, "Nutricionista", ativo=False
    ),
]

# A grade precisa ter TEXTURA: horários de pico cheios e horários vazios.
# Sem isso a agenda fica uniforme e não demonstra nada.
#
# (índice do paciente, dia da semana, hora, meses de casa)
# dia: 1=segunda … 6=sábado
GRADE_PILATES: list[tuple[int, int, int, int]] = [
    # ── SEGUNDA 08:00 — TURMA COMPLETA (4/4) ────────────────────────────────
    # É aqui que a demonstração mostra a quinta matrícula sendo recusada.
    (0, 1, 8, 7),
    (1, 1, 8, 5),
    (2, 1, 8, 3),
    (3, 1, 8, 2),
    # ── SEGUNDA 19:00 — pico da noite, quase cheio (3/4) ────────────────────
    (4, 1, 19, 6),
    (5, 1, 19, 4),
    (6, 1, 19, 2),
    # ── QUARTA 08:00 — mesma turma da manhã de segunda (3/4) ────────────────
    (0, 3, 8, 7),
    (1, 3, 8, 5),
    (2, 3, 8, 3),
    # ── QUARTA 19:00 ────────────────────────────────────────────────────────
    (4, 3, 19, 6),
    (5, 3, 19, 4),
    # ── TERÇA 07:00 — turma pequena da madrugada (2/4) ──────────────────────
    (7, 2, 7, 4),
    (8, 2, 7, 3),
    # ── QUINTA 07:00 ────────────────────────────────────────────────────────
    (7, 4, 7, 4),
    (8, 4, 7, 3),
    # ── TERÇA 18:00 ─────────────────────────────────────────────────────────
    (9, 2, 18, 5),
    (10, 2, 18, 2),
    # ── SEXTA 09:00 — só uma pessoa, bastante vaga ──────────────────────────
    (11, 5, 9, 1),
    # ── SÁBADO 09:00 — sábado tem movimento, mas menos ──────────────────────
    (12, 6, 9, 3),
    (13, 6, 9, 2),
    # 10:00, 11:00, 14:00 a 17:00 e 20:00 ficam VAZIOS de propósito: é onde a
    # recepção encontra vaga para reposição durante a demonstração.
]


@dataclass
class ResultadoDemo:
    pacientes: int = 0
    matriculas: int = 0
    sessoes: int = 0
    reservas: int = 0
    faltas_justificadas: int = 0
    faltas_nao_justificadas: int = 0
    reposicoes_feitas: int = 0
    cancelamentos: int = 0
    presencas: int = 0
    pacotes: int = 0
    cobrancas_pagas: int = 0
    cobrancas_pendentes: int = 0
    cobrancas_vencidas: int = 0
    avisos: list[str] = field(default_factory=list)


def _ultimo_dia_31_antes_de(referencia: date) -> date:
    """Dia 31 mais recente antes da referência.

    Percorre para trás até achar um mês que tenha 31 dias — janeiro, março,
    maio, julho, agosto, outubro ou dezembro.
    """
    d = referencia.replace(day=1)
    for _ in range(12):
        d = (d - timedelta(days=1)).replace(day=1)
        try:
            return d.replace(day=31)
        except ValueError:
            continue
    return referencia


def _primeira_data_do_dia(a_partir_de: date, dia_semana: int) -> date:
    delta = (dia_semana - ((a_partir_de.weekday() + 1) % 7)) % 7
    return a_partir_de + timedelta(days=delta)


def limpar(db: DbSession) -> dict[str, int]:
    """Remove tudo que o seed criou, na ordem das dependências.

    Identifica os registros pela marca `[demo]` nas observações do paciente.
    Dado digitado à mão durante a demonstração não é tocado.
    """
    ids = list(
        db.execute(select(Patient.id).where(Patient.observacoes.like(f"{MARCA_DEMO}%"))).scalars()
    )
    if not ids:
        return {"pacientes": 0}

    contagem: dict[str, int] = {}

    def apagar(stmt: Delete) -> int:
        """DELETE devolvendo a contagem de linhas removidas.

        `Session.execute` é tipado como devolvendo `Result`, que não expõe
        `rowcount`; um DELETE devolve na verdade um `CursorResult`, que expõe.
        O cast diz isso ao mypy sem desligar a checagem do módulo.
        """
        return cast("CursorResult[Any]", db.execute(stmt)).rowcount

    # Ordem importa: filhos antes dos pais.
    contagem["cobrancas"] = apagar(delete(Charge).where(Charge.patient_id.in_(ids)))
    contagem["reservas"] = apagar(delete(Booking).where(Booking.patient_id.in_(ids)))
    contagem["pacotes"] = apagar(delete(Package).where(Package.patient_id.in_(ids)))
    matriculas = list(
        db.execute(select(Enrollment.id).where(Enrollment.patient_id.in_(ids))).scalars()
    )
    if matriculas:
        apagar(delete(EnrollmentHorario).where(EnrollmentHorario.enrollment_id.in_(matriculas)))
    contagem["matriculas"] = apagar(delete(Enrollment).where(Enrollment.patient_id.in_(ids)))

    # Sessões sem nenhuma reserva sobrando são lixo do seed.
    orfas = list(
        db.execute(
            select(Session.id).where(
                ~select(Booking.id).where(Booking.session_id == Session.id).exists()
            )
        ).scalars()
    )
    if orfas:
        contagem["sessoes"] = apagar(delete(Session).where(Session.id.in_(orfas)))

    contagem["blackouts"] = apagar(delete(Blackout).where(Blackout.motivo.like(f"{MARCA_DEMO}%")))
    contagem["pacientes"] = apagar(delete(Patient).where(Patient.id.in_(ids)))
    db.commit()
    return contagem


def _criar_pacientes(db: DbSession) -> list[Patient]:
    hoje = date.today()
    criados = []
    for seq, p in enumerate(PACIENTES, start=1):
        paciente = Patient(
            nome_completo=p.nome,
            cpf=_cpf_invalido(seq),
            # Idade relativa a hoje, para o número não envelhecer no banco.
            data_nascimento=date(hoje.year - p.idade, ((seq * 7) % 12) + 1, (seq % 28) + 1),
            sexo=p.sexo,
            estado_civil=p.estado_civil,
            profissao=p.profissao,
            email=f"{p.nome.split()[0].lower()}.demo@exemplo.invalido",
            telefone=_tel(seq),
            emergencia_nome=f"Contato de {p.nome.split()[0]}",
            emergencia_telefone=_tel(seq + 100),
            observacoes=f"{MARCA_DEMO} paciente fictício de demonstração",
            consentimento_lgpd=True,
            consentimento_em=hoje - timedelta(days=seq * 3),
            ativo=p.ativo,
        )
        db.add(paciente)
        criados.append(paciente)
    db.flush()
    return criados


def _criar_matriculas(
    db: DbSession,
    pacientes: list[Patient],
    pilates: Service,
    instrutor: User,
    r: ResultadoDemo,
) -> list[Enrollment]:
    hoje = date.today()
    matriculas: list[Enrollment] = []

    for idx, (i_pac, dia, hora, meses) in enumerate(GRADE_PILATES):
        paciente = pacientes[i_pac]

        # Uma matrícula por paciente; horários adicionais entram na existente.
        existente = next((m for m in matriculas if m.patient_id == paciente.id), None)
        if existente is not None:
            existente.horarios.append(
                EnrollmentHorario(dia_semana=dia, hora_inicio=time(hour=hora))
            )
            db.flush()
            continue

        # Vencimentos em dias diferentes do mês.
        inicio = hoje - timedelta(days=meses * 30 + idx)
        if i_pac == 3:
            # DIA 31 de propósito: é o caso que quebra em meses de 30 dias e
            # em fevereiro. Na tela, as competências dele mostram o ciclo
            # encaixando no último dia existente de cada mês.
            inicio = _ultimo_dia_31_antes_de(hoje - timedelta(days=meses * 30))

        matricula = Enrollment(
            patient_id=paciente.id,
            service_id=pilates.id,
            professional_id=instrutor.id,
            vigencia_inicio=inicio,
            # FICTÍCIO — a cliente não informou valores (docs/premissas.md P2).
            valor_mensal_centavos=18_000 + (i_pac % 4) * 2_000,
            dia_vencimento=inicio.day,
            horarios=[EnrollmentHorario(dia_semana=dia, hora_inicio=time(hour=hora))],
        )
        db.add(matricula)
        db.flush()
        matriculas.append(matricula)
        r.matriculas += 1

    return matriculas


def _historico_de_presenca(db: DbSession, recepcao_id: int, r: ResultadoDemo) -> None:
    """Marca presença, falta e cancelamento nas sessões que já passaram.

    Sem histórico, "sessões do mês" e "taxa de ocupação" ficam em zero e o
    dashboard não mostra se o cálculo está certo.
    """
    agora = datetime.now(tz=FUSO)
    passadas = list(
        db.execute(
            select(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(Session.inicia_em < agora, Booking.status == StatusReserva.AGENDADA)
            .order_by(Session.inicia_em)
        )
        .scalars()
        .all()
    )

    for i, reserva in enumerate(passadas):
        # ~78% presença, o resto dividido entre falta e cancelamento — é a
        # proporção que faz a taxa de ocupação parecer de um studio real.
        if i % 9 == 3:
            reserva.status = StatusReserva.FALTA
            justificada = i % 18 == 3
            reserva.justificada = justificada
            reserva.motivo_justificativa = "Atestado médico" if justificada else None
            if justificada:
                r.faltas_justificadas += 1
            else:
                r.faltas_nao_justificadas += 1
        elif i % 11 == 5:
            reserva.status = StatusReserva.CANCELADA
            reserva.cancelado_em = agora - timedelta(days=1)
            reserva.motivo_cancelamento = (
                "Avisou que não vem" if i % 22 == 5 else "Viagem a trabalho"
            )
            r.cancelamentos += 1
        else:
            reserva.status = StatusReserva.PRESENTE
            r.presencas += 1
    db.flush()


def _faltas_recentes_com_prazo_apertado(db: DbSession, r: ResultadoDemo) -> None:
    """Garante faltas justificadas no MÊS CORRENTE, algumas perto do prazo.

    O painel de reposições só mostra faltas dentro da janela. Sem isto, o
    histórico geraria pendências já vencidas e o painel apareceria vazio na
    demonstração — justamente a tela mais importante.
    """
    hoje = date.today()
    inicio_do_mes = hoje.replace(day=1)
    agora = datetime.now(tz=FUSO)

    candidatas = list(
        db.execute(
            select(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(
                Session.inicia_em >= datetime.combine(inicio_do_mes, time.min, tzinfo=FUSO),
                Session.inicia_em < agora,
                Booking.status == StatusReserva.PRESENTE,
            )
            .order_by(Session.inicia_em.desc())
        )
        .scalars()
        .all()
    )

    # Quatro faltas justificadas recentes: três pendentes e uma que será
    # reposta logo abaixo, para o vínculo aparecer na tela.
    for reserva in candidatas[:4]:
        reserva.status = StatusReserva.FALTA
        reserva.justificada = True
        reserva.motivo_justificativa = "Atestado médico"
        r.presencas -= 1
        r.faltas_justificadas += 1

    # Duas não justificadas, para contrastar no painel.
    for reserva in candidatas[4:6]:
        reserva.status = StatusReserva.FALTA
        reserva.justificada = False
        r.presencas -= 1
        r.faltas_nao_justificadas += 1

    # Uma justificada do MÊS PASSADO, cuja janela já fechou. Só aparece com
    # "Mostrar prazos vencidos" marcado — é o que demonstra que o prazo
    # existe e é aplicado.
    #
    # NOTA: com a janela em "mês do calendário", o prazo restante é igual para
    # todas as faltas do mês corrente. "Prazo apertado" aparece naturalmente
    # conforme o mês avança, não é algo que o seed possa forçar sem falsear a
    # regra.
    anterior = db.execute(
        select(Booking)
        .join(Session, Session.id == Booking.session_id)
        .where(
            Session.inicia_em < datetime.combine(inicio_do_mes, time.min, tzinfo=FUSO),
            Booking.status == StatusReserva.PRESENTE,
        )
        .order_by(Session.inicia_em.desc())
        .limit(1)
    ).scalar_one_or_none()
    if anterior is not None:
        anterior.status = StatusReserva.FALTA
        anterior.justificada = True
        anterior.motivo_justificativa = "Atestado médico (prazo de reposição vencido)"
        r.presencas -= 1
        r.faltas_justificadas += 1

    db.flush()


def _uma_reposicao_ja_feita(db: DbSession, recepcao_id: int, r: ResultadoDemo) -> None:
    """Repõe UMA das faltas, para o vínculo `substitui_booking_id` aparecer."""
    from app.services import reposicao_service, schedule_service

    pendentes = reposicao_service.listar_pendentes(db)
    if not pendentes:
        r.avisos.append("Nenhuma falta pendente para repor — reposição não criada.")
        return

    alvo = pendentes[-1]
    de, ate = reposicao_service.periodo_para_oferecer(db, alvo)
    vagas = schedule_service.sessoes_com_vaga(
        db, de=de, ate=ate, excluir_patient_id=alvo.patient_id
    )

    if not vagas:
        r.avisos.append("Nenhum horário com vaga — reposição de exemplo não criada.")
        return

    booking_service.criar(
        db,
        session_id=vagas[0].sessao.id,
        patient_id=alvo.patient_id,
        criado_por_id=recepcao_id,
        origem=OrigemReserva.REPOSICAO,
        substitui_booking_id=alvo.booking_id,
    )
    r.reposicoes_feitas += 1


def _pacotes(
    db: DbSession, pacientes: list[Patient], fisio: Service, admin_id: int, r: ResultadoDemo
) -> None:
    """Pacotes com saldos diferentes, um perto de vencer."""
    from app.services import package_service

    hoje = date.today()
    # (paciente, sessões, valor em centavos, dias até vencer, sessões já usadas)
    # Valores FICTÍCIOS — a cliente não informou preço (docs/premissas.md P3).
    combinacoes = [
        (14, 10, 90_000, 60, 0),  # recém-comprado, saldo cheio
        (15, 10, 90_000, 5, 7),  # PERTO DE VENCER, saldo 3
        (16, 6, 55_000, 45, 4),  # meio do caminho, saldo 2
        (17, 12, 108_000, None, 1),  # sem validade: vale até acabar
    ]
    for i_pac, sessoes, valor, dias, usadas in combinacoes:
        pacote, _ = package_service.vender(
            db,
            patient_id=pacientes[i_pac].id,
            service_id=fisio.id,
            sessoes_contratadas=sessoes,
            valor_centavos=valor,
            validade_ate=hoje + timedelta(days=dias) if dias is not None else None,
            comprado_em=hoje - timedelta(days=30 - (dias or 0) // 2),
            registrado_por_id=admin_id,
        )
        r.pacotes += 1
        _consumir_sessoes_do_pacote(db, pacote, pacientes[i_pac], fisio, admin_id, usadas, r)


def _consumir_sessoes_do_pacote(
    db: DbSession,
    pacote: Package,
    paciente: Patient,
    fisio: Service,
    instrutor_id: int,
    quantas: int,
    r: ResultadoDemo,
) -> None:
    """Cria sessões passadas de fisioterapia com presença, gastando o saldo.

    Só `presente` consome sessão — é a definição que vale (CLAUDE.md).
    """
    if quantas == 0:
        return
    agora = datetime.now(tz=FUSO)
    criadas = 0
    dias_atras = 3

    while criadas < quantas and dias_atras < 90:
        quando = (agora - timedelta(days=dias_atras)).replace(minute=0, second=0, microsecond=0)
        # Fisioterapia acontece nos horários que o Pilates deixa vazios —
        # 10h, 11h, 15h, 16h — para a grade ter textura e não colidir.
        quando = quando.replace(hour=[10, 11, 15, 16][criadas % 4])
        dias_atras += 4

        if quando.weekday() == 6:  # domingo: studio fechado
            continue

        sessao = _sessao_livre_para(db, fisio, instrutor_id, quando)
        if sessao is None:
            continue

        try:
            db.add(
                Booking(
                    session_id=sessao.id,
                    patient_id=paciente.id,
                    package_id=pacote.id,
                    posicao=_proxima_posicao_livre(db, sessao),
                    capacidade_sessao=sessao.capacidade,
                    origem=OrigemReserva.AVULSA,
                    status=StatusReserva.PRESENTE,
                    criado_por_id=instrutor_id,
                )
            )
            db.flush()
        except IntegrityError:
            db.rollback()
            continue

        r.reservas += 1
        criadas += 1

    if criadas < quantas:
        r.avisos.append(
            f"Pacote de {paciente.nome_completo}: só {criadas} de {quantas} "
            "sessões consumidas (não havia horário livre)."
        )


def _sessao_livre_para(
    db: DbSession, servico: Service, instrutor_id: int, quando: datetime
) -> Session | None:
    """Sessão existente naquele instante, ou uma nova se o instrutor estiver livre.

    Respeita a constraint da Fase 3 — um instrutor não ministra duas turmas
    começando no mesmo instante. O seed obedece às mesmas regras do sistema;
    fosse diferente, estaria testando outra coisa.
    """
    existente = db.execute(
        select(Session).where(
            Session.service_id == servico.id,
            Session.professional_id == instrutor_id,
            Session.inicia_em == quando,
        )
    ).scalar_one_or_none()
    if existente is not None:
        return existente

    conflito = db.execute(
        select(Session.id).where(
            Session.professional_id == instrutor_id, Session.inicia_em == quando
        )
    ).first()
    if conflito is not None:
        return None

    sessao = Session(
        service_id=servico.id,
        professional_id=instrutor_id,
        inicia_em=quando,
        termina_em=quando + timedelta(minutes=servico.duracao_min),
        capacidade=servico.capacidade_padrao,
    )
    db.add(sessao)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return sessao


def _proxima_posicao_livre(db: DbSession, sessao: Session) -> int:
    ocupadas = {
        p
        for p in db.execute(
            select(Booking.posicao).where(
                Booking.session_id == sessao.id,
                Booking.status != StatusReserva.CANCELADA,
            )
        ).scalars()
    }
    for posicao in range(1, sessao.capacidade + 1):
        if posicao not in ocupadas:
            return posicao
    return sessao.capacidade


def _pagamentos(db: DbSession, recepcao_id: int, r: ResultadoDemo) -> None:
    """Deixa as cobranças em todos os três estados visíveis na tela.

    O alvo é um studio que parece saudável, não falido: a maioria paga,
    algumas em atraso e algumas do ciclo seguinte ainda a vencer.

    "Vencida" nunca é gravada — é `pendente` com vencimento no passado. Para
    haver pendente NÃO vencida, o faturamento vai até o próximo ciclo: o
    studio cobra o mês adiantado, e o vencimento cai no início do ciclo.
    """
    hoje = date.today()
    cobrancas = list(
        db.execute(select(Charge).order_by(Charge.patient_id, Charge.vencimento)).scalars()
    )

    # Uma em cada quatro cobranças já vencidas fica em aberto — o suficiente
    # para o card "Total Vencido" ter número sem parecer inadimplência geral.
    vencidas_em_aberto = 0
    for i, cobranca in enumerate(cobrancas):
        if cobranca.vencimento > hoje:
            continue  # ciclo seguinte: fica pendente, e não vencida
        if i % 4 == 1 and vencidas_em_aberto < 8:
            vencidas_em_aberto += 1
            continue
        cobranca.status = StatusCobranca.PAGO
        cobranca.pago_em = datetime.combine(cobranca.vencimento, time(10, 0), tzinfo=UTC)
        cobranca.forma_pagamento = FormaPagamento.PIX if i % 2 == 0 else FormaPagamento.DINHEIRO
        cobranca.registrado_por_id = recepcao_id
    db.flush()

    for cobranca in cobrancas:
        if cobranca.status is StatusCobranca.PAGO:
            r.cobrancas_pagas += 1
        elif cobranca.vencimento < hoje:
            r.cobrancas_vencidas += 1
        else:
            r.cobrancas_pendentes += 1


def semear(db: DbSession) -> ResultadoDemo:
    """Monta o studio de demonstração. Idempotente: limpa antes de recriar."""
    r = ResultadoDemo()

    servicos = {s.nome: s for s in db.execute(select(Service)).scalars()}
    pilates = servicos.get("Pilates")
    fisio = servicos.get("Fisioterapia")
    if pilates is None or fisio is None:
        raise RuntimeError("Serviços não encontrados. Rode antes: python -m app.cli seed-servicos")

    usuarios = {u.papel: u for u in db.execute(select(User)).scalars()}
    recepcao = usuarios.get(Papel.RECEPCAO)
    instrutor = usuarios.get(Papel.INSTRUTOR) or usuarios.get(Papel.ADMIN)
    admin = usuarios.get(Papel.ADMIN)
    if recepcao is None or instrutor is None or admin is None:
        raise RuntimeError("Usuários não encontrados. Rode antes: python -m app.cli seed-usuarios")

    limpar(db)

    pacientes = _criar_pacientes(db)
    r.pacientes = len(pacientes)

    _criar_matriculas(db, pacientes, pilates, instrutor, r)

    # Materializa 8 semanas à frente E o histórico para trás, para o dashboard
    # ter sessões do mês corrente.
    hoje = date.today()
    geracao = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)
    r.sessoes += geracao.sessoes_criadas
    r.reservas += geracao.reservas_criadas
    _gerar_historico_para_tras(db, recepcao.id, hoje, r)

    _historico_de_presenca(db, recepcao.id, r)
    _faltas_recentes_com_prazo_apertado(db, r)
    _uma_reposicao_ja_feita(db, recepcao.id, r)

    _pacotes(db, pacientes, fisio, admin.id, r)

    # Até o próximo ciclo: sem isso toda cobrança teria vencimento no
    # passado, e não haveria "pendente" que não estivesse vencida.
    charge_service.gerar_mensalidades(db, ate=hoje + timedelta(days=31))
    _pagamentos(db, recepcao.id, r)

    db.commit()
    return r


def _gerar_historico_para_tras(
    db: DbSession, recepcao_id: int, hoje: date, r: ResultadoDemo
) -> None:
    """Materializa as sessões passadas de cada matrícula, desde o início do mês.

    O gerador da Fase 4 só olha para frente — é o comportamento certo em
    produção, mas deixa o dashboard sem "sessões do mês". Aqui o histórico é
    criado explicitamente, e SÓ no seed de demonstração.
    """
    inicio = max(hoje.replace(day=1) - timedelta(days=31), hoje - timedelta(days=60))
    servicos = {s.id: s for s in db.execute(select(Service)).scalars()}

    for matricula in db.execute(select(Enrollment)).scalars().unique():
        servico = servicos[matricula.service_id]
        for horario in matricula.horarios:
            dia = _primeira_data_do_dia(max(inicio, matricula.vigencia_inicio), horario.dia_semana)
            while dia < hoje:
                momento = datetime.combine(dia, horario.hora_inicio, tzinfo=FUSO)
                sessao = db.execute(
                    select(Session).where(
                        Session.service_id == matricula.service_id,
                        Session.professional_id == matricula.professional_id,
                        Session.inicia_em == momento,
                    )
                ).scalar_one_or_none()
                if sessao is None:
                    sessao = Session(
                        service_id=matricula.service_id,
                        professional_id=matricula.professional_id,
                        inicia_em=momento,
                        termina_em=momento + timedelta(minutes=servico.duracao_min),
                        capacidade=servico.capacidade_padrao,
                    )
                    db.add(sessao)
                    db.flush()
                    r.sessoes += 1

                ja_tem = db.execute(
                    select(Booking.id).where(
                        Booking.session_id == sessao.id,
                        Booking.patient_id == matricula.patient_id,
                        Booking.status != StatusReserva.CANCELADA,
                    )
                ).first()
                if ja_tem is None:
                    try:
                        booking_service.criar(
                            db,
                            session_id=sessao.id,
                            patient_id=matricula.patient_id,
                            criado_por_id=recepcao_id,
                            origem=OrigemReserva.RECORRENTE,
                            enrollment_id=matricula.id,
                        )
                        r.reservas += 1
                    except Exception:
                        db.rollback()
                dia += timedelta(days=7)
    db.flush()
