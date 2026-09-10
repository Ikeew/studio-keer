import { Mail, Phone, ShieldCheck, ShieldAlert } from 'lucide-react'

import { data, inicial, telefone } from '@/lib/formato'
import {
  ESTADO_CIVIL_LABEL,
  SEXO_LABEL,
  type Paciente,
} from '@/types/paciente'

type Props = {
  paciente: Paciente
  onEditar: (p: Paciente) => void
  onVerMatriculas: (p: Paciente) => void
}

function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[15px]">
      <span className="text-muted">{rotulo}:</span>
      <span className="text-right">{valor}</span>
    </div>
  )
}

export function PacienteCard({ paciente, onEditar, onVerMatriculas }: Props) {
  return (
    <article className="flex flex-col rounded-card border border-edge bg-surface p-6 shadow-card">
      <div className="mb-4 flex items-start justify-between">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand text-lg font-semibold text-white">
          {inicial(paciente.nome_completo)}
        </div>
        {paciente.consentimento_lgpd ? (
          <span
            className="flex items-center gap-1 text-sm text-muted"
            title={`Consentimento LGPD em ${data(paciente.consentimento_em)}`}
          >
            <ShieldCheck size={16} /> LGPD
          </span>
        ) : (
          <span
            className="flex items-center gap-1 text-sm text-danger"
            title="Consentimento LGPD não registrado"
          >
            <ShieldAlert size={16} /> Sem consentimento
          </span>
        )}
      </div>

      <h3 className="font-heading text-xl font-semibold">{paciente.nome_completo}</h3>
      {!paciente.ativo && (
        <span className="mt-1 self-start rounded-full bg-edge px-2 py-0.5 text-sm text-muted">
          Inativo
        </span>
      )}

      <div className="mt-4 flex flex-col gap-1">
        {paciente.idade !== null && <Linha rotulo="Idade" valor={`${paciente.idade} anos`} />}
        {paciente.profissao && <Linha rotulo="Profissão" valor={paciente.profissao} />}
        <Linha rotulo="Sexo" valor={SEXO_LABEL[paciente.sexo]} />
        {paciente.cpf_formatado && <Linha rotulo="CPF" valor={paciente.cpf_formatado} />}
        <Linha rotulo="Estado Civil" valor={ESTADO_CIVIL_LABEL[paciente.estado_civil]} />
      </div>

      {(paciente.email || paciente.telefone) && (
        <div className="mt-4 flex flex-col gap-2 border-t border-edge pt-4 text-[15px]">
          {paciente.email && (
            <span className="flex items-center gap-2 text-muted">
              <Mail size={16} /> <span className="truncate">{paciente.email}</span>
            </span>
          )}
          {paciente.telefone && (
            <span className="flex items-center gap-2 text-muted">
              <Phone size={16} /> {telefone(paciente.telefone)}
            </span>
          )}
        </div>
      )}

      {paciente.emergencia_nome && (
        <div className="mt-3 rounded-card bg-subtle px-3 py-2 text-sm">
          <span className="text-muted">Emergência: </span>
          {paciente.emergencia_nome}
          {paciente.emergencia_telefone && ` · ${telefone(paciente.emergencia_telefone)}`}
        </div>
      )}

      {/* mt-auto empurra o bloco para a base do card: sem isso, cards de
          alturas diferentes na mesma linha ficam com os botões desalinhados. */}
      <div className="mt-auto flex gap-2 pt-5">
        <button
          type="button"
          onClick={() => onEditar(paciente)}
          className="flex-1 rounded-card bg-edge py-3 text-[15px] font-medium transition-colors hover:bg-edge/70"
        >
          Editar
        </button>
        <button
          type="button"
          onClick={() => onVerMatriculas(paciente)}
          className="flex-1 rounded-card bg-edge py-3 text-[15px] font-medium transition-colors hover:bg-edge/70"
        >
          Matrículas
        </button>
      </div>
    </article>
  )
}
