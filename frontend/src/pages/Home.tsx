import { useEffect, useState } from "react";
import { checkHealth, getRoot, type RootResponse } from "@/lib/api";

export default function Home() {
  const [apiInfo, setApiInfo] = useState<RootResponse | null>(null);
  const [isHealthy, setIsHealthy] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [root, health] = await Promise.all([getRoot(), checkHealth()]);
        setApiInfo(root);
        setIsHealthy(health.status === "healthy");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to connect to API");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-2xl w-full mx-auto p-8 space-y-6">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">
            IsTheTubeRunning
          </h1>
          <p className="text-muted-foreground text-lg">
            TfL Disruption Alert System
          </p>
        </div>

        <div className="border rounded-lg p-6 space-y-4 bg-card">
          <h2 className="text-xl font-semibold">System Status</h2>

          {loading && (
            <div className="text-muted-foreground">Connecting to backend...</div>
          )}

          {error && (
            <div className="text-destructive">
              <p className="font-semibold">Connection Error</p>
              <p className="text-sm">{error}</p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure the backend is running at http://localhost:8000
              </p>
            </div>
          )}

          {!loading && !error && apiInfo && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={`h-3 w-3 rounded-full ${isHealthy ? "bg-green-500" : "bg-red-500"}`} />
                <span className="font-medium">
                  {isHealthy ? "Backend Connected" : "Backend Unavailable"}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                <p>API: {apiInfo.message}</p>
                <p>Version: {apiInfo.version}</p>
              </div>
            </div>
          )}
        </div>

        <div className="text-center text-sm text-muted-foreground">
          <p>Phase 1: Project Foundation Complete</p>
        </div>
      </div>
    </div>
  );
}
