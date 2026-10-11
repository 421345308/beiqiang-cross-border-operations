// Repair identical Windows Path aliases before entering upstream's safety boundary.
// Different values remain an error; credentials and telemetry rules are unchanged.
import path from 'node:path';
import { runSafeSpawn } from './upstream/erduo-broll-loop-engineering/scripts/safe-spawn.mjs';

export function windowsEnvironment(source) {
  const result = { ...source };
  const aliases = Object.keys(result).filter((key) => key.toLowerCase() === 'path');
  const value = aliases.length ? result[aliases[0]] : '';
  if (aliases.some((key) => result[key] !== value)) {
    throw new Error('Conflicting Windows PATH aliases; launch stopped.');
  }
  for (const key of aliases) delete result[key];
  result.PATH = `${path.dirname(process.execPath)}${path.delimiter}${value}`;
  return result;
}

try {
  const env = process.platform === 'win32' ? windowsEnvironment(process.env) : process.env;
  process.exitCode = runSafeSpawn(process.argv.slice(2), { env });
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 64;
}
