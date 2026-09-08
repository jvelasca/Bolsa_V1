import { spawnSync } from 'node:child_process';
import { ROOT, logError, logInfo } from './lib/logger.mjs';

/**
 * pnpm db:backup:cron:win — registra (o imprime instrucciones para) las tareas
 * programadas de Windows de PREVENCIÓN/DR sobre la BD local `bolsa_v1`.
 *   - `db:dump` DIARIO (backup 3-2-1 → db-backups local + espejo opcional).
 *   - `db:dr:test` DIARIO por defecto (restore-test COMPLETO de volumen real:
 *     dump + checksum + restore a scratch + Alembic head + integridad de datos
 *     financiera y de mercado). V2.15.5: el restore-test periódico ya no se limita
 *     al CI con BD vacía; el scheduler local cubre la BD con datos reales.
 * SOLO Windows; SOLO la BD local `bolsa_v1`. Best-effort de conveniencia.
 *
 *   node scripts/db-backup-cron-win.mjs                       # imprime comandos schtasks
 *   node scripts/db-backup-cron-win.mjs --install [--at 18:00] [--at-dr 03:30]
 *   node scripts/db-backup-cron-win.mjs --install --no-dr      # solo el backup diario
 */

const withFlag = (f) => process.argv.includes(f);
function flagValue(flag) {
  const idx = process.argv.indexOf(flag);
  return idx >= 0 ? process.argv[idx + 1] : undefined;
}

const TASK_DUMP = 'BolsaV1_DB_Backup';
const TASK_DR = 'BolsaV1_DR_RestoreTest';
const DEFAULT_TIME = '18:00';
const DEFAULT_DR_TIME = '03:30';

/** Una línea schtasks que registra `pnpm <cmd>` en `name` con horario diario. */
function schtasksCommand(name, cmd, time) {
  const pnpm = `"${ROOT.replace(/"/g, '\\"')}\\node_modules\\.bin\\pnpm.cmd"`;
  const inner = `cd /d "${ROOT.replace(/"/g, '\\"')}" && ${pnpm} ${cmd}`;
  const escapedInner = inner.replace(/"/g, '\\"');
  return `schtasks /create /tn "${name}" /tr "cmd /c \\"${escapedInner}\\"" /sc daily /st ${time} /f`;
}

function main() {
  if (process.platform !== 'win32') {
    logInfo('db-backup:cron:win', 'Tarea programada solo aplica a Windows (schtasks). En otro SO usa cron/systemd-timer.');
    process.exit(0);
  }

  const dumpTime = flagValue('--at') ?? DEFAULT_TIME;
  const drTime = flagValue('--at-dr') ?? DEFAULT_DR_TIME;
  const withDr = !withFlag('--no-dr');
  const cmdDump = schtasksCommand(TASK_DUMP, 'db:dump', dumpTime);
  const cmdDr = schtasksCommand(TASK_DR, 'db:dr:test', drTime);

  if (withFlag('--install')) {
    logInfo('db-backup:cron:win', `Registrando backup diario "${TASK_DUMP}" a las ${dumpTime}...`);
    const r1 = spawnSync(cmdDump, [], { shell: true, encoding: 'utf8', stdio: 'inherit' });
    if (r1.status !== 0) {
      logError('db-backup:cron:win', 'schtasks devolvió error para el backup diario; revisa permisos (terminal como administrador).');
      process.exit(1);
    }
    logInfo('db-backup:cron:win', `Tarea "${TASK_DUMP}" registrada.`);
    if (withDr) {
      logInfo('db-backup:cron:win', `Registrando restore-test de DR "${TASK_DR}" a las ${drTime}...`);
      const r2 = spawnSync(cmdDr, [], { shell: true, encoding: 'utf8', stdio: 'inherit' });
      if (r2.status !== 0) {
        logError('db-backup:cron:win', 'schtasks devolvió error para el restore-test de DR; revisa permisos.');
        process.exit(1);
      }
      logInfo('db-backup:cron:win', `Tarea "${TASK_DR}" registrada.`);
    }
    logInfo('db-backup:cron:win', 'Para consultar/eliminar:');
    logInfo('db-backup:cron:win', `  schtasks /query /tn "${TASK_DUMP}"   ·   schtasks /query /tn "${TASK_DR}"`);
    logInfo('db-backup:cron:win', `  schtasks /delete /tn "${TASK_DUMP}" /f   ·   schtasks /delete /tn "${TASK_DR}" /f`);
    return;
  }

  logInfo('db-backup:cron:win', 'Programación Windows (copia y ejecuta SCHTASKS como administrador):');
  console.log(cmdDump);
  if (withDr) {
    console.log(cmdDr);
  }
  logInfo('db-backup:cron:win', 'Para registrarlo aquí mismo: node scripts/db-backup-cron-win.mjs --install [--at 18:00] [--at-dr 03:30] [--no-dr]');
}

main();
