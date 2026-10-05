import { useId } from 'react'

import type { useMarcarPago } from '@/api/financeiro'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { reais } from '@/lib/formato'
import { FORMAS_PAGAMENTO, FORMA_LABEL, type Cobranca } from '@/types/financeiro'

function mensagemDeErro(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string'
    ? d
    : 'Não foi possível registrar o pagamento. Tente de novo em instantes.'
}

function motivoDeNaoPendente(atual: Cobranca | undefined): string {
  if (atual?.status === 'pago') {
    // "Outro" não diz nada como forma; melhor omitir do que escrever "via Outro".
    const forma = atual.forma_pagamento
    return forma && forma !== 'outro'
      ? `Esta cobrança não está mais pendente: já foi paga via ${FORMA_LABEL[forma]}.`
      : 'Esta cobrança não está mais pendente: já foi paga.'
  }
  if (atual?.status === 'cancelado') {
    return 'Esta cobrança não está mais pendente: foi cancelada.'
  }
  return 'Esta cobrança não está mais pendente.'
}

/**
 * Baixa de uma cobrança com a forma que o paciente usou de verdade.
 *
 * Antes, toda baixa virava PIX, e o gráfico de formas de pagamento do
 * dashboard mentiria: PIX apareceria como a forma mais usada mesmo que
 * ninguém pagasse assim. Por isso não há forma pré-selecionada — deixar PIX
 * marcado por padrão recriaria o mesmo viés.
 *
 * Um clique já registra, sem passo de confirmação: se a recepção errar a
 * forma, o "Desfazer" da tabela corrige.
 *
 * A mutação vem de fora: ela precisa sobreviver ao modal, senão um erro que
 * chega depois do fechamento some e a recepção sai achando que deu baixa.
 */
export function RegistrarPagamento({
  cobranca,
  atual,
  pagar,
  onPronto,
}: {
  /** Retrato de quando o modal abriu: só para exibir paciente, descrição e valor. */
  cobranca: Cobranca
  /** A mesma cobrança na lista atual; ausente se saiu da página. */
  atual: Cobranca | undefined
  pagar: ReturnType<typeof useMarcarPago>
  onPronto: () => void
}) {
  const perguntaId = useId()
  // A forma em registro sai da própria mutação, não de um estado paralelo.
  const formaEmRegistro = pagar.isPending ? pagar.variables?.forma : undefined
  // Outra recepcionista pode ter dado baixa, ou a proprietária cancelado.
  // O caso típico é a lista estar velha: o clique dá 409, a lista é refeita
  // na falha e aí o motivo aparece. Fora de pending e success: após a baixa
  // daqui, a lista é refeita antes do onSuccess fechar o modal, e o aviso piscaria.
  const naoPendente = (pagar.isIdle || pagar.isError) && atual?.status !== 'pendente'

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="font-medium">{cobranca.paciente_nome}</p>
        <p className="text-muted">{cobranca.descricao}</p>
        <p className="mt-2 font-heading text-2xl font-semibold">
          {reais(cobranca.valor_centavos)}
        </p>
      </div>

      {naoPendente ? (
        <>
          <Aviso tipo="info">{motivoDeNaoPendente(atual)}</Aviso>
          <Button variante="secundario" onClick={onPronto}>
            Fechar
          </Button>
        </>
      ) : (
        <div role="group" aria-labelledby={perguntaId} className="flex flex-col gap-3">
          <p id={perguntaId} className="text-[15px] font-medium">
            Como o paciente pagou?
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {FORMAS_PAGAMENTO.map((forma) => {
              const registrando = formaEmRegistro === forma
              return (
                <button
                  key={forma}
                  type="button"
                  disabled={pagar.isPending}
                  aria-busy={registrando || undefined}
                  onClick={() =>
                    pagar.mutate(
                      { id: cobranca.id, forma },
                      { onSuccess: () => onPronto() },
                    )
                  }
                  className={cn(
                    'rounded-card border border-edge bg-surface px-4 py-3 text-[15px] font-medium transition-colors hover:border-brand hover:text-brand focus-visible:outline-brand',
                    'disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-edge disabled:hover:text-ink',
                    // A forma clicada continua legível e destacada enquanto registra.
                    registrando &&
                      'border-brand text-brand disabled:opacity-100 disabled:hover:border-brand disabled:hover:text-brand',
                  )}
                >
                  {registrando ? 'Registrando…' : FORMA_LABEL[forma]}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Com o motivo já explicado acima, o 409 cru só repetiria a notícia. Se a
          cobrança saiu da página (filtro "Pendentes"), o aviso acima é genérico
          e a mensagem do servidor é a única que diz o que aconteceu. */}
      {pagar.isError && !(naoPendente && atual) && (
        <Aviso tipo="erro">{mensagemDeErro(pagar.error)}</Aviso>
      )}
    </div>
  )
}
