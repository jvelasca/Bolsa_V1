-- RFC-008 — Catálogo ART-PROFILE + asociación cuenta.active_profile_id
-- Migra settings_json.investorProfile embebido → filas + limpia la clave JSON.

CREATE TABLE IF NOT EXISTS "investor_profiles" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "version" TEXT NOT NULL DEFAULT '1.0.0',
  "user_id" TEXT,
  "horizon" TEXT NOT NULL,
  "objectives" JSONB NOT NULL DEFAULT '[]',
  "risk_tolerance" TEXT NOT NULL,
  "experience" TEXT NOT NULL,
  "max_acceptable_loss_pct" DECIMAL(8, 4),
  "notes" TEXT,
  "suggested_policy_template_id" TEXT NOT NULL,
  "selected_policy_template_id" TEXT NOT NULL,
  "observed_json" JSONB,
  "updated_by" TEXT NOT NULL DEFAULT 'user',
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "investor_profiles_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "investor_profiles_user_id_idx"
  ON "investor_profiles"("user_id");
CREATE INDEX IF NOT EXISTS "investor_profiles_updated_at_idx"
  ON "investor_profiles"("updated_at" DESC);

ALTER TABLE "investment_accounts"
  ADD COLUMN IF NOT EXISTS "active_profile_id" TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'investment_accounts_active_profile_id_fkey'
  ) THEN
    ALTER TABLE "investment_accounts"
      ADD CONSTRAINT "investment_accounts_active_profile_id_fkey"
      FOREIGN KEY ("active_profile_id") REFERENCES "investor_profiles"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS "investment_accounts_active_profile_id_idx"
  ON "investment_accounts"("active_profile_id");

-- Backfill desde settings_json.investorProfile
DO $$
DECLARE
  r RECORD;
  p JSONB;
  pid TEXT;
BEGIN
  FOR r IN
    SELECT id, name, user_id, settings_json
    FROM investment_accounts
    WHERE settings_json ? 'investorProfile'
      AND settings_json->'investorProfile' IS NOT NULL
      AND jsonb_typeof(settings_json->'investorProfile') = 'object'
  LOOP
    p := r.settings_json->'investorProfile';
    IF COALESCE(p->'declared'->>'horizon', p->>'horizon') IS NULL THEN
      CONTINUE;
    END IF;

    pid := COALESCE(NULLIF(p->>'profileId', ''), 'PROF-' || substr(md5(r.id), 1, 12));

    INSERT INTO investor_profiles (
      id, name, version, user_id,
      horizon, objectives, risk_tolerance, experience,
      max_acceptable_loss_pct, notes,
      suggested_policy_template_id, selected_policy_template_id,
      observed_json, updated_by, created_at, updated_at
    ) VALUES (
      pid,
      COALESCE(NULLIF(p->>'name', ''), 'Perfil · ' || r.name),
      COALESCE(NULLIF(p->>'version', ''), '1.0.0'),
      r.user_id,
      COALESCE(p->'declared'->>'horizon', p->>'horizon'),
      COALESCE(p->'declared'->'objectives', p->'objectives', '[]'::jsonb),
      COALESCE(p->'declared'->>'riskTolerance', p->>'riskTolerance', 'moderate'),
      COALESCE(p->'declared'->>'experience', p->>'experience', 'intermediate'),
      NULLIF(COALESCE(p->'declared'->>'maxAcceptableLossPct', p->>'maxAcceptableLossPct'), '')::decimal,
      COALESCE(p->'declared'->>'notes', p->>'notes'),
      COALESCE(NULLIF(p->>'suggestedPolicyTemplateId', ''), 'moderate'),
      COALESCE(
        NULLIF(p->>'selectedPolicyTemplateId', ''),
        NULLIF(p->>'suggestedPolicyTemplateId', ''),
        'moderate'
      ),
      p->'observed',
      'user',
      COALESCE((p->>'createdAt')::timestamptz, CURRENT_TIMESTAMP),
      COALESCE((p->>'updatedAt')::timestamptz, CURRENT_TIMESTAMP)
    )
    ON CONFLICT (id) DO NOTHING;

    UPDATE investment_accounts
    SET active_profile_id = pid
    WHERE id = r.id AND active_profile_id IS NULL;

    UPDATE investment_accounts
    SET settings_json = settings_json - 'investorProfile'
    WHERE id = r.id;
  END LOOP;
END $$;
