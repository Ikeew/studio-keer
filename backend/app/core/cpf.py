"""Validação de CPF pelos dígitos verificadores.

Contar 11 caracteres não valida nada: "12345678900" tem 11 dígitos e é
inválido. A recepção digita CPF o dia inteiro, e um dígito trocado só
aparece meses depois, quando alguém precisa do documento.
"""

import re

SOMENTE_DIGITOS = re.compile(r"\D")


def normalizar_cpf(valor: str) -> str:
    """Remove pontuação. '123.456.789-00' -> '12345678900'."""
    return SOMENTE_DIGITOS.sub("", valor)


def cpf_valido(valor: str) -> bool:
    cpf = normalizar_cpf(valor)

    if len(cpf) != 11:
        return False

    # Sequências de dígito repetido passam no cálculo dos verificadores, mas
    # não são CPFs válidos. Precisam ser recusadas à parte.
    if cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False

    return True


def formatar_cpf(cpf: str) -> str:
    """'12345678900' -> '123.456.789-00', para exibição."""
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
