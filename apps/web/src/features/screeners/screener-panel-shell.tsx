import type { LucideIcon } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ScreenerPanelShellProps {
  embedded?: boolean;
  title: string;
  description?: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
  headerClassName?: string;
}

export function ScreenerPanelShell({
  embedded,
  title,
  description,
  icon: Icon,
  children,
  className,
  headerClassName,
}: ScreenerPanelShellProps) {
  if (embedded) {
    return <div className={cn("space-y-4 min-w-0", className)}>{children}</div>;
  }

  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader className={cn("pb-3", headerClassName)}>
        <CardTitle className="flex items-center gap-2 text-base">
          {Icon && <Icon className="h-4 w-4 text-primary" />}
          {title}
        </CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
