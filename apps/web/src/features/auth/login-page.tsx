import { useState } from 'react';
import { BarChart3, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/stores/auth-store';

export function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de acceso');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md border-border/80 shadow-2xl">
        <CardHeader className="space-y-3 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/15">
            <BarChart3 className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">Bolsa V1</CardTitle>
          <p className="text-sm text-muted-foreground">Plataforma de análisis bursátil</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-border bg-muted/40 py-2 pl-10 pr-3 text-sm outline-none ring-primary focus:ring-1"
                  placeholder="Introduce la contraseña"
                  autoFocus
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading || !password}>
              {loading ? 'Accediendo…' : 'Acceder'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
