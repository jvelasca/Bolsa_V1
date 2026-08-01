import { useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { cn } from '@/lib/utils';

import { api } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';

import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { usePendingOrders } from '@/features/trading/use-pending-orders';



type OperationsTab = 'open' | 'pending';



export function OperationsPanel() {

  const [tab, setTab] = useState<OperationsTab>('open');

  const { pendingOrders, removePendingOrder } = usePendingOrders();



  const accountScope = useActiveAccountQueryKey();

  const portfolioQuery = useQuery({

    queryKey: ['portfolio', accountScope],

    queryFn: api.getPortfolio,

    staleTime: 15_000,

  });



  const positions = portfolioQuery.data?.data.positions ?? [];



  return (

    <div className="flex h-full min-h-0 flex-col">

      <div className="scroll-area flex shrink-0 gap-0.5 overflow-x-auto border-b border-border px-1">

        {(

          [

            ['open', 'Operaciones abiertas'],

            ['pending', 'Operaciones pendientes'],

          ] as const

        ).map(([id, label]) => (

          <button

            key={id}

            type="button"

            onClick={() => setTab(id)}

            className={cn(

              'px-2 py-1 text-[11px] font-medium',

              tab === id

                ? 'border-b-2 border-primary text-foreground'

                : 'text-muted-foreground hover:text-foreground',

            )}

          >

            {label}

            {id === 'open' && positions.length > 0 && (

              <span className="ml-1 opacity-70">({positions.length})</span>

            )}

            {id === 'pending' && pendingOrders.length > 0 && (

              <span className="ml-1 opacity-70">({pendingOrders.length})</span>

            )}

          </button>

        ))}

      </div>



      {tab === 'open' && (

        <div className="scroll-area min-h-0 flex-1 overflow-auto">

          {portfolioQuery.isLoading && (

            <p className="p-3 text-xs text-muted-foreground">Cargando cartera…</p>

          )}

          {portfolioQuery.isError && (

            <p className="p-3 text-xs text-destructive">No se pudo cargar la cartera</p>

          )}

          {!portfolioQuery.isLoading && positions.length === 0 && (

            <p className="p-4 text-center text-xs text-muted-foreground">Sin posiciones abiertas</p>

          )}

          {positions.length > 0 && (

            <table className="w-full text-[11px]">

              <thead className="sticky top-0 bg-card/95 text-muted-foreground">

                <tr className="border-b border-border">

                  <th className="px-2 py-1 text-left font-medium">Símbolo</th>

                  <th className="px-2 py-1 text-right font-medium">Qty</th>

                  <th className="px-2 py-1 text-right font-medium">Precio</th>

                  <th className="px-2 py-1 text-right font-medium">Valor</th>

                  <th className="px-2 py-1 text-right font-medium">P&amp;L</th>

                </tr>

              </thead>

              <tbody>

                {positions.map((pos) => {

                  const pnlUp = (pos.unrealizedPnl ?? 0) >= 0;

                  return (

                    <tr key={pos.id} className="border-b border-border/50 hover:bg-accent/30">

                      <td className="px-2 py-1">

                        <div className="font-medium">{pos.symbol}</div>

                        <div className="truncate text-[10px] text-muted-foreground">{pos.name}</div>

                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">{pos.quantity}</td>

                      <td className="px-2 py-1 text-right tabular-nums">

                        {pos.lastPrice != null ? formatPrice(pos.lastPrice) : '—'}

                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">

                        {pos.marketValue != null ? formatPrice(pos.marketValue) : '—'}

                      </td>

                      <td

                        className={cn(

                          'px-2 py-1 text-right tabular-nums',

                          pnlUp ? 'text-emerald-400' : 'text-red-400',

                        )}

                      >

                        {pos.unrealizedPnl != null ? formatPrice(pos.unrealizedPnl) : '—'}

                        {pos.unrealizedPnlPct != null && (

                          <span className="ml-1 text-[10px] opacity-80">

                            ({formatPct(pos.unrealizedPnlPct)})

                          </span>

                        )}

                      </td>

                    </tr>

                  );

                })}

              </tbody>

            </table>

          )}

        </div>

      )}



      {tab === 'pending' && (

        <div className="scroll-area min-h-0 flex-1 overflow-auto">

          {pendingOrders.length === 0 && (

            <p className="p-4 text-center text-xs text-muted-foreground">

              Sin órdenes pendientes — crea una stop/limitada desde el diálogo de operación.

            </p>

          )}

          {pendingOrders.length > 0 && (

            <table className="w-full text-[11px]">

              <thead className="sticky top-0 bg-card/95 text-muted-foreground">

                <tr className="border-b border-border">

                  <th className="px-2 py-1 text-left font-medium">Símbolo</th>

                  <th className="px-2 py-1 text-left font-medium">Tipo</th>

                  <th className="px-2 py-1 text-right font-medium">Qty</th>

                  <th className="px-2 py-1 text-right font-medium">Precio</th>

                  <th className="px-2 py-1 text-right font-medium"></th>

                </tr>

              </thead>

              <tbody>

                {pendingOrders.map((order) => (

                  <tr key={order.id} className="border-b border-border/50 hover:bg-accent/30">

                    <td className="px-2 py-1 font-medium">{order.symbol}</td>

                    <td className="px-2 py-1 capitalize">

                      {order.side === 'buy' ? 'Compra' : 'Venta'} limitada

                    </td>

                    <td className="px-2 py-1 text-right tabular-nums">{order.quantity}</td>

                    <td className="px-2 py-1 text-right tabular-nums">

                      {formatPrice(order.limitPrice)}

                    </td>

                    <td className="px-2 py-1 text-right">

                      <button

                        type="button"

                        className="text-[10px] text-muted-foreground hover:text-destructive"

                        onClick={() => void removePendingOrder(order.id)}

                      >

                        Cancelar

                      </button>

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          )}

        </div>

      )}

    </div>

  );

}

