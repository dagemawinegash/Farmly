"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

type AuthMeResponse = {
  onboarding_completed: boolean;
};

export default function MainPage() {
  const router = useRouter();
  const { accessToken, clearToken, isHydrated } = useAuth();
  const [checkingOnboarding, setCheckingOnboarding] = useState(true);

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      router.replace("/auth-options");
      return;
    }

    api
      .get<AuthMeResponse>("/api/auth/me")
      .then(({ data }) => {
        if (!data?.onboarding_completed) {
          router.replace("/onboarding/location");
          return;
        }
        setCheckingOnboarding(false);
      })
      .catch(() => {
        clearToken();
        router.replace("/auth-options");
      });
  }, [accessToken, clearToken, isHydrated, router]);

  if (!isHydrated || checkingOnboarding) return null;

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6">
      <div className="mx-auto w-full max-w-3xl rounded-[var(--radius)] border border-border bg-card p-6 sm:p-8">
        <h1 className="text-2xl font-bold">Farmly Main Page</h1>
        <p className="mt-2 text-sm text-muted">
          Authentication is complete. Chat-first interface will be implemented in the next phase.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link href="/">
            <Button variant="outline">Go to Landing</Button>
          </Link>
          <Button
            onClick={() => {
              clearToken();
              window.location.href = "/auth-options";
            }}
          >
            Logout
          </Button>
        </div>
      </div>
    </main>
  );
}
