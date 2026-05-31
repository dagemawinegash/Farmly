import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  CheckCircle,
  CloudRain,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { alertsApi } from "@/lib/alerts";
import { extractErrorMessage } from "@/lib/errors";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const severityStyles = {
  high: {
    card: "border-red-200 bg-red-50",
    badge: "bg-red-600 text-white",
    icon: "text-red-600",
  },
  medium: {
    card: "border-amber-200 bg-amber-50",
    badge: "bg-amber-500 text-white",
    icon: "text-amber-600",
  },
  low: {
    card: "border-green-200 bg-green-50",
    badge: "bg-green-600 text-white",
    icon: "text-green-700",
  },
};

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function AlertCard({ alert, onMarkRead, onDelete }) {
  const styles = severityStyles[alert.severity] || severityStyles.low;
  const forecast = alert.raw_weather?.forecast_days?.slice(0, 5) || [];

  return (
    <Card className={`${styles.card} overflow-hidden`}>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-full bg-white/80 p-2 shadow-sm">
            {alert.severity === "low" ? (
              <ShieldCheck className={`h-5 w-5 ${styles.icon}`} />
            ) : (
              <AlertTriangle className={`h-5 w-5 ${styles.icon}`} />
            )}
          </div>
          <div>
            <CardTitle className="text-lg">{alert.title}</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {formatDate(alert.created_at)}
              {alert.location_used ? ` - ${alert.location_used}` : ""}
            </p>
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold capitalize ${styles.badge}`}>
          {alert.severity}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-sm leading-6 text-foreground">{alert.message}</p>
        {alert.action_text && (
          <div className="rounded-xl border border-white/70 bg-white/75 p-3 text-sm leading-6">
            <p className="font-semibold text-foreground">What to do</p>
            <p className="mt-1 text-muted-foreground">{alert.action_text}</p>
          </div>
        )}

        {forecast.length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {forecast.map((day) => (
              <div key={day.date} className="rounded-xl border border-white/70 bg-white/70 p-2 text-xs">
                <p className="font-semibold text-foreground">{day.date}</p>
                <p className="mt-1 text-muted-foreground">Rain: {day.rain_mm ?? "-"} mm</p>
                <p className="text-muted-foreground">Max: {day.temp_max_c ?? "-"} C</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {!alert.is_read && (
            <Button variant="outline" size="sm" onClick={() => onMarkRead(alert.alert_id)} className="gap-2 bg-white/80">
              <CheckCircle className="h-4 w-4" />
              Mark as read
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDelete(alert.alert_id)}
            className="gap-2 border-red-200 bg-white/80 text-red-700 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AlertsPage() {
  const navigate = useNavigate();
  const { accessToken, isHydrated } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
      return;
    }
    loadAlerts();
  }, [accessToken, isHydrated, navigate]);

  const unreadCount = useMemo(() => alerts.filter((alert) => !alert.is_read).length, [alerts]);

  async function loadAlerts() {
    setLoading(true);
    setError("");
    try {
      const { data } = await alertsApi.listAlerts();
      setAlerts(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Could not load alerts."));
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateWeatherAlerts() {
    setGenerating(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await alertsApi.generateWeatherAlerts();
      setAlerts((previous) => [...data.alerts, ...previous]);
      setSuccess(`${data.generated_count} weather alert${data.generated_count === 1 ? "" : "s"} generated.`);
    } catch (err) {
      setError(extractErrorMessage(err, "Could not generate weather alerts."));
    } finally {
      setGenerating(false);
    }
  }

  async function handleMarkRead(alertId) {
    try {
      const { data } = await alertsApi.markRead(alertId);
      setAlerts((previous) =>
        previous.map((alert) => (alert.alert_id === alertId ? data.alert : alert))
      );
    } catch (err) {
      setError(extractErrorMessage(err, "Could not update alert."));
    }
  }

  async function handleDeleteAlert(alertId) {
    if (!confirm("Delete this alert?")) return;
    setError("");
    setSuccess("");
    try {
      await alertsApi.deleteAlert(alertId);
      setAlerts((previous) => previous.filter((alert) => alert.alert_id !== alertId));
      setSuccess("Alert deleted.");
    } catch (err) {
      setError(extractErrorMessage(err, "Could not delete alert."));
    }
  }

  if (!isHydrated || loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-background">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dcfce7,transparent_34%),var(--background)]">
      <header className="border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <Link to="/main-page" className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Chat
          </Link>
          <Button onClick={handleGenerateWeatherAlerts} disabled={generating} className="gap-2">
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Check weather alerts
          </Button>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <div className="mb-5 rounded-3xl border border-green-100 bg-white/85 p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-primary">
                <Bell className="h-5 w-5" />
                <span className="text-sm font-bold uppercase tracking-wide">Farmly Alerts</span>
              </div>
              <h1 className="mt-3 text-2xl font-extrabold text-foreground sm:text-3xl">
                Weather risks for your farm
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                Farmly checks the next 5 days of weather and turns risky conditions into simple actions farmers can follow.
              </p>
            </div>
            <div className="rounded-2xl border border-green-100 bg-green-50 px-4 py-3 text-sm text-green-800">
              <p className="font-bold">{unreadCount} unread</p>
              <p className="text-xs">Weather-only MVP</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {success}
          </div>
        )}

        {alerts.length === 0 ? (
          <div className="grid place-items-center rounded-3xl border border-dashed border-green-200 bg-white/75 px-6 py-16 text-center">
            <CloudRain className="h-10 w-10 text-primary" />
            <h2 className="mt-4 text-xl font-bold">No alerts yet</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
              Click "Check weather alerts" to generate alerts from your saved farm location.
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {alerts.map((alert) => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                onMarkRead={handleMarkRead}
                onDelete={handleDeleteAlert}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
