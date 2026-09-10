import pytest

from app.core.cpf import cpf_valido, formatar_cpf, normalizar_cpf


class TestCpfValido:
    @pytest.mark.parametrize(
        "cpf",
        [
            "529.982.247-25",
            "52998224725",
            "111.444.777-35",
            "11144477735",
        ],
    )
    def test_aceita_cpf_valido_com_e_sem_pontuacao(self, cpf: str) -> None:
        assert cpf_valido(cpf)

    @pytest.mark.parametrize(
        ("cpf", "motivo"),
        [
            ("52998224724", "último dígito verificador errado"),
            ("52998224715", "penúltimo dígito verificador errado"),
            ("123456789", "curto demais"),
            ("529982247250", "longo demais"),
            ("", "vazio"),
            ("abcdefghijk", "sem dígitos"),
        ],
    )
    def test_recusa_cpf_invalido(self, cpf: str, motivo: str) -> None:
        assert not cpf_valido(cpf), motivo

    @pytest.mark.parametrize(
        "cpf",
        ["00000000000", "11111111111", "99999999999", "123.123.123-12"],
    )
    def test_recusa_sequencia_de_digito_repetido(self, cpf: str) -> None:
        """Passam no cálculo dos verificadores, mas não são CPF válido.

        É o caso que uma validação ingênua deixa entrar.
        """
        assert not cpf_valido(cpf)


def test_normalizar_remove_pontuacao() -> None:
    assert normalizar_cpf("529.982.247-25") == "52998224725"


def test_formatar_para_exibicao() -> None:
    assert formatar_cpf("52998224725") == "529.982.247-25"
