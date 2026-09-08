import { spawnSync } from 'node:child_process';
import { ROOT, logError, logInfo } from './lib/logger.mjs';

/**
 * pnpm db:backup:cron:win — registra (o imprime instrucciones para) una tarea
 * programada de Windows que ejecuta `pnpm db:dump` diariamente sobre esta copia
 * local. SOLO Windows; SOLO la BD local `bolsa_v1`.
 *
 *   node scripts/db-backup-cron-win.mjs            # imprime el comando schtasks recomendado
 *   node scripts/db-backup-cron-win.mjs --install [--at 18:00]
 */

const withFlag = (f) => process.argv.includes(f);
function flagValue(flag) {
  const idx = process.argv.indexOf(flag);
  return idx >= 0 ? process.argv[idx + 1] : undefined;
}

const TASK_NAME = 'BolsaV1_DB_Backup';
const DEFAULT_TIME = '18:00';

/** Devuelve la línea schtasks que registra la tarea diaria. */
export function schtasksCommand(time = DEFAULT_TIME) {
  const pnpm = `"${ROOT.replace(/"/g, '\\"')}\\node_modules\\.bin\\pnpm.cmd"`;
  const inner = `cd /d "${ROOT.replace(/"/g, '\\"')}" && ${pnpm} db:dump`;
  const escapedInner = inner.replace(/"/g, '\\"');
  return `schtasks /create /tn "${TASK_NAME}" /tr "cmd /c \\"${escapedInner}\\"" /sc daily /st ${time} /f`;
}

function main() {
  if (process.platform !== 'win32') {
    logInfo('db-backup:cron:win', 'Tarea programada solo aplica a Windows (schtasks). En otro SO usa cron/systemd-timer.');
    process.exit(0);
  }

  const time = flagValue('--at') ?? DEFAULT_TIME;
  const cmd = schtasksCommand(time);

  if (withFlag('--install')) {
    logInfo('db-backup:cron:win', `Registrando tarea "${TASK_NAME}" diaria a las ${time}...`);
    const res = spawnSync(cmd, [], { shell: true, encoding: 'utf8', stdio: 'inherit' });
    if (res.status !== 0) {
      logError('db-backup:cron:win', 'schtasks devolvió error; revisa permisos (terminal como administrador).');
      process.exit(1);
    }
    logInfo('db-backup:cron:win', `Tarea "${TASK_NAME}" registrada. Para editarla a mano o desinstalarla:`);
    logInfo('db-backup:cron:win', `  schtasks /query /tn "${TASK_NAME}"`);
    logInfo('db-backup:cron:win', `  schtasks /delete /tn "${TASK_NAME}" /f`);
    return;
  }

  logInfo('db-backup:cron:win', 'Backup diario de bolsa_v1 — copia y ejecuta como administrador:');
  console.log(cmd);
  logInfo('db-backup:cron:win', 'Para registrarlo aquí mismo: node scripts/db-backup-cron-win.mjs --install');
}

main();
