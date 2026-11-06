/**
 * RFC-008 — Catálogo ART-PROFILE (solo CRUD, sin asignación).
 * Declared ≠ Policy; Observed solo lectura.
 *
 * Este panel vive en Configuración → Perfil inversor y es SOLO catálogo: no elige cuenta,
 * no asigna y no crea perfiles al montarse. La asignación de un perfil a una cuenta existe
 * únicamente en Cuentas → ficha → Configuración.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type {
  ExperienceLevel,
  InvestmentAccountDto,
  InvestorProfileV1,
  ProfileHorizon,
  RiskTolerance,
  SuggestablePolicyTemplateId,
} from "@bolsa/shared";
import {
  POLICY_TEMPLATE_LABELS,
  formatExitPolicyPreview,
  formatPortfolioFitPreview,
  getTradingPolicyTemplate,
  observeInvestorProfile,
  suggestPolicyTemplateFromDeclared,
} from "@bolsa/shared";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { profileUsageByAccount } from "@/features/accounts/investor-profile-picker";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const HORIZON_OPTIONS: { id: ProfileHorizon; label: string }[] = [
  { id: "intraday", label: "Intradía" },
  { id: "swing", label: "Swing (días–semanas)" },
  { id: "position", label: "Posicional (semanas–meses)" },
  { id: "long_term", label: "Largo plazo" },
];

const RISK_OPTIONS: { id: RiskTolerance; label: string; hint: string }[] = [
  { id: "low", label: "Baja", hint: "Preservar capital" },
  { id: "moderate", label: "Moderada", hint: "Equilibrio" },
  { id: "high", label: "Alta", hint: "Mayor volatilidad aceptada" },
];

const EXPERIENCE_OPTIONS: { id: ExperienceLevel; label: string }[] = [
  { id: "novice", label: "Principiante" },
  { id: "intermediate", label: "Intermedio" },
  { id: "advanced", label: "Avanzado" },
  { id: "professional", label: "Profesional" },
];

const OBJECTIVE_OPTIONS = [
  { id: "preservation", label: "Preservación" },
  { id: "income", label: "Renta / dividendos" },
  { id: "growth", label: "Crecimiento" },
  { id: "speculation", label: "Especulación" },
] as const;

const TEMPLATE_OPTIONS: SuggestablePolicyTemplateId[] = [
  "conservative",
  "moderate",
  "aggressive_swing",
];

interface DraftState {
  name: string;
  horizon: ProfileHorizon;
  riskTolerance: RiskTolerance;
  experience: ExperienceLevel;
  objectives: string[];
  maxAcceptableLossPct: string;
  selectedPolicyTemplateId: SuggestablePolicyTemplateId | null;
  followSuggestion: boolean;
}

function emptyDraft(): DraftState {
  return {
    name: "",
    horizon: "swing",
    riskTolerance: "moderate",
    experience: "intermediate",
    objectives: ["growth"],
    maxAcceptableLossPct: "",
    selectedPolicyTemplateId: null,
    followSuggestion: true,
  };
}

function draftFromProfile(p: InvestorProfileV1 | null | undefined): DraftState {
  if (!p) return emptyDraft();
  const suggested = p.suggestedPolicyTemplateId as SuggestablePolicyTemplateId;
  const selected = p.selectedPolicyTemplateId as SuggestablePolicyTemplateId;
  return {
    name: p.name,
    horizon: p.declared.horizon,
    riskTolerance: p.declared.riskTolerance,
    experience: p.declared.experience,
    objectives: [...p.declared.objectives],
    maxAcceptableLossPct:
      p.declared.maxAcceptableLossPct != null
        ? String(p.declared.maxAcceptableLossPct)
        : "",
    selectedPolicyTemplateId: selected,
    followSuggestion: suggested === selected,
  };
}

interface InvestorProfilePanelProps {
  /** Cuentas del usuario, solo para mostrar el uso del catálogo (lectura). */
  accounts?: InvestmentAccountDto[];
  onSaved?: () => void;
}

export function InvestorProfilePanel({
  accounts = [],
  onSaved,
}: InvestorProfilePanelProps) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftState>(emptyDraft);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"edit" | "create">("edit");

  const listQuery = useQuery({
    queryKey: ["investor-profiles"],
    queryFn: async () => (await api.listInvestorProfiles()).data,
  });

  const profiles = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  useEffect(() => {
    if (mode === "create") {
      setDraft(emptyDraft());
      return;
    }
    const current = profiles.find((p) => p.profileId === selectedId) ?? null;
    setDraft(draftFromProfile(current));
    setError(null);
  }, [selectedId, profiles, mode]);

  const declaredPreview = useMemo(
    () => ({
      horizon: draft.horizon,
      riskTolerance: draft.riskTolerance,
      experience: draft.experience,
      objectives: draft.objectives,
      maxAcceptableLossPct: draft.maxAcceptableLossPct
        ? Number(draft.maxAcceptableLossPct)
        : undefined,
    }),
    [draft],
  );

  const suggested = useMemo(
    () => suggestPolicyTemplateFromDeclared(declaredPreview),
    [declaredPreview],
  );

  const selected: SuggestablePolicyTemplateId = draft.followSuggestion
    ? suggested
    : (draft.selectedPolicyTemplateId ?? suggested);

  const policyPreview = useMemo(
    () => getTradingPolicyTemplate(selected),
    [selected],
  );
  const observedPreview = useMemo(
    () => observeInvestorProfile(declaredPreview, []),
    [declaredPreview],
  );

  const saveMutation = useMutation({
    mutationFn: async () => {
      const loss = draft.maxAcceptableLossPct.trim()
        ? Number(draft.maxAcceptableLossPct)
        : undefined;
      if (loss != null && (Number.isNaN(loss) || loss < 0 || loss > 100)) {
        throw new Error("Pérdida máxima aceptable debe estar entre 0 y 100");
      }
      if (draft.objectives.length === 0) {
        throw new Error("Selecciona al menos un objetivo");
      }
      const name = draft.name.trim() || "Perfil sin nombre";
      const body = {
        name,
        horizon: draft.horizon,
        riskTolerance: draft.riskTolerance,
        experience: draft.experience,
        objectives: [...draft.objectives],
        maxAcceptableLossPct: loss ?? null,
        suggestedPolicyTemplateId: suggested,
        selectedPolicyTemplateId: selected,
      };
      if (mode === "create" || !selectedId) {
        return (await api.createInvestorProfile(body)).data;
      }
      return (await api.updateInvestorProfile(selectedId, body)).data;
    },
    onSuccess: (p) => {
      void queryClient.invalidateQueries({ queryKey: ["investor-profiles"] });
      setSelectedId(p.profileId);
      setMode("edit");
      setError(null);
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (profileId: string) => api.deleteInvestorProfile(profileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["investor-profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setSelectedId(null);
      setMode("create");
      onSaved?.();
    },
    onError: (err: Error) =>
      setError(
        /profile_in_use|en uso/i.test(err.message)
          ? "No se puede eliminar: el perfil está en uso. Reasigna sus cuentas antes de borrarlo."
          : err.message,
      ),
  });

  function toggleObjective(id: string) {
    setDraft((prev) => {
      const has = prev.objectives.includes(id);
      return {
        ...prev,
        objectives: has
          ? prev.objectives.filter((x) => x !== id)
          : [...prev.objectives, id],
      };
    });
  }

  const usage = useMemo(() => profileUsageByAccount(accounts), [accounts]);
  const selectedProfile =
    profiles.find((p) => p.profileId === selectedId) ?? null;
  const selectedUsedBy = selectedId ? (usage[selectedId] ?? []) : [];

  return (
    <div className="space-y-5 text-sm">
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
        <p className="font-medium text-foreground">
          Catálogo reutilizable de perfiles
        </p>
        <p className="mt-1">
          Los perfiles viven en un{" "}
          <span className="text-foreground">catálogo por usuario</span> y varias
          cuentas pueden compartir el mismo. Aquí solo se crean, editan y
          eliminan: la asignación se hace en{" "}
          <span className="text-foreground">
            Cuentas → [cuenta] → Configuración
          </span>
          .
        </p>
      </div>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Perfiles del catálogo</h3>
          <button
            type="button"
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-accent"
            onClick={() => {
              setMode("create");
              setSelectedId(null);
              setDraft(emptyDraft());
            }}
          >
            + Nuevo perfil
          </button>
        </div>

        {listQuery.isLoading ? (
          <p className="text-xs text-muted-foreground">Cargando catálogo…</p>
        ) : null}
        {listQuery.isError ? (
          <p className="text-xs text-destructive">
            No se pudo cargar el catálogo. ¿Está la API en marcha?
          </p>
        ) : null}
        {!listQuery.isLoading && profiles.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Aún no hay perfiles en el catálogo. Pulsa «+ Nuevo perfil» para
            crear el primero.
          </p>
        ) : null}

        {profiles.length > 0 ? (
          <ul className="space-y-1.5">
            {profiles.map((p) => {
              const isEditing = mode === "edit" && selectedId === p.profileId;
              const usedBy = usage[p.profileId] ?? [];
              const templateLabel =
                POLICY_TEMPLATE_LABELS[
                  p.selectedPolicyTemplateId as SuggestablePolicyTemplateId
                ] ?? p.selectedPolicyTemplateId;
              return (
                <li
                  key={p.profileId}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2.5",
                    isEditing ? "border-primary bg-primary/5" : "border-border",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => {
                      setMode("edit");
                      setSelectedId(p.profileId);
                    }}
                  >
                    <div className="font-medium text-foreground">{p.name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {templateLabel} · {p.declared.horizon} · riesgo{" "}
                      {p.declared.riskTolerance}
                    </div>
                    <div
                      className="text-[11px] text-muted-foreground"
                      data-testid={`profile-usage-${p.profileId}`}
                    >
                      {usedBy.length > 0
                        ? `En uso en: ${usedBy.join(", ")}`
                        : "Sin uso"}
                    </div>
                  </button>
                  <div className="flex shrink-0 gap-2">
                    {usedBy.length > 0 ? (
                      <span className="rounded-md border border-emerald-500/40 px-2 py-1 text-[11px] text-emerald-700 dark:text-emerald-400">
                        En uso ({usedBy.length})
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="text-[11px] text-muted-foreground hover:text-foreground hover:underline"
                      onClick={() => {
                        setMode("edit");
                        setSelectedId(p.profileId);
                      }}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      className="text-[11px] text-destructive hover:underline disabled:text-muted-foreground disabled:no-underline"
                      disabled={deleteMutation.isPending || usedBy.length > 0}
                      title={
                        usedBy.length > 0
                          ? "En uso: reasigna sus cuentas antes de eliminar el perfil"
                          : undefined
                      }
                      onClick={() => {
                        if (window.confirm(`¿Eliminar perfil «${p.name}»?`)) {
                          deleteMutation.mutate(p.profileId);
                        }
                      }}
                    >
                      Eliminar
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

      <section className="space-y-3 rounded-md border border-dashed border-border p-3">
        <h3 className="font-medium">
          {mode === "create" ? "Crear perfil" : "Editar perfil seleccionado"}
        </h3>

        {mode === "edit" && selectedProfile && selectedUsedBy.length > 0 ? (
          <p
            className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-300"
            data-testid="profile-shared-warning"
          >
            Este perfil lo usan {selectedUsedBy.length}{" "}
            {selectedUsedBy.length === 1 ? "cuenta" : "cuentas"} (
            {selectedUsedBy.join(", ")}). Al guardar cambia la Trading Policy de
            todas ellas.
          </p>
        ) : null}
        <FieldRow label="Nombre del perfil">
          <input
            className={inputClassName}
            value={draft.name}
            onChange={(e) => setDraft((p) => ({ ...p, name: e.target.value }))}
            placeholder="p. ej. Swing moderado"
          />
        </FieldRow>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Horizonte
          </h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {HORIZON_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDraft((p) => ({ ...p, horizon: opt.id }))}
                className={cn(
                  "rounded-md border px-3 py-2 text-left text-sm",
                  draft.horizon === opt.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-accent",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Aversión al riesgo
          </h4>
          <div className="grid gap-2 sm:grid-cols-3">
            {RISK_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() =>
                  setDraft((p) => ({ ...p, riskTolerance: opt.id }))
                }
                className={cn(
                  "rounded-md border px-3 py-2 text-left text-sm",
                  draft.riskTolerance === opt.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-accent",
                )}
              >
                <div className="font-medium">{opt.label}</div>
                <div className="text-[10px] text-muted-foreground">
                  {opt.hint}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Experiencia
          </h4>
          <div className="flex flex-wrap gap-2">
            {EXPERIENCE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDraft((p) => ({ ...p, experience: opt.id }))}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs",
                  draft.experience === opt.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-accent",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Objetivos
          </h4>
          <div className="flex flex-wrap gap-2">
            {OBJECTIVE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleObjective(opt.id)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs",
                  draft.objectives.includes(opt.id)
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-accent",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <FieldRow label="Pérdida máxima aceptable (% cuenta, opcional)">
          <input
            className={inputClassName}
            value={draft.maxAcceptableLossPct}
            onChange={(e) =>
              setDraft((p) => ({ ...p, maxAcceptableLossPct: e.target.value }))
            }
            placeholder="p. ej. 1.5"
            inputMode="decimal"
          />
        </FieldRow>

        <div className="space-y-2 rounded-md border border-border p-3">
          <h4 className="font-medium">Trading Policy (plantilla)</h4>
          <p className="text-xs text-muted-foreground">
            Sugerida: {POLICY_TEMPLATE_LABELS[suggested]}. Puedes override.
          </p>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={draft.followSuggestion}
              onChange={(e) =>
                setDraft((p) => ({ ...p, followSuggestion: e.target.checked }))
              }
            />
            Seguir sugerencia automática
          </label>
          {!draft.followSuggestion ? (
            <div className="flex flex-wrap gap-2">
              {TEMPLATE_OPTIONS.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() =>
                    setDraft((p) => ({
                      ...p,
                      selectedPolicyTemplateId: id,
                      followSuggestion: false,
                    }))
                  }
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-xs",
                    selected === id
                      ? "border-primary bg-primary/5"
                      : "border-border",
                  )}
                >
                  {POLICY_TEMPLATE_LABELS[id]}
                </button>
              ))}
            </div>
          ) : null}
          <p className="text-[10px] text-muted-foreground">
            Riesgo/trade {policyPreview.risk.maxRiskPerTradePct}% · R:R{" "}
            {policyPreview.risk.minRewardToRiskRatio} · max pos.{" "}
            {policyPreview.exposure.maxOpenPositions}
          </p>
          {policyPreview.exit ? (
            <p
              className="text-[10px] text-muted-foreground"
              data-testid="investor-profile-exit-policy"
            >
              {formatExitPolicyPreview(policyPreview.exit)}
            </p>
          ) : null}
          <p
            className="text-[10px] text-muted-foreground"
            data-testid="investor-profile-portfolio-fit"
          >
            {formatPortfolioFitPreview(policyPreview)}
          </p>
        </div>

        <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">
            Perfil observado (solo lectura)
          </p>
          <p className="mt-1">
            Muestras: {observedPreview.sampleTradeCount}
            {observedPreview.notes?.[0] ? ` · ${observedPreview.notes[0]}` : ""}
          </p>
        </div>
      </section>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {saveMutation.isPending
            ? "Guardando…"
            : mode === "create"
              ? "Crear en el catálogo"
              : "Guardar cambios del perfil"}
        </button>
      </div>
    </div>
  );
}
