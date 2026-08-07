import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Registrar el plugin react-hooks para que las reglas existan (el código ya
    // usa `eslint-disable react-hooks/exhaustive-deps` por todo el frontend).
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      // Reglas que el frontend ya utiliza y espera activas. Se dejan como
      // warning para no romper el lint legacy (160 calls condicionales de
      // hooks y deps pendientes se auditan en la refactor F4·8) mientras se
      // mantiene la visibilidad de la deuda.
      'react-hooks/rules-of-hooks': 'warn',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    ignores: ['**/dist/**', '**/node_modules/**', '**/.turbo/**'],
  },
  {
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
);
