"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { SUPPORTED_LANGUAGES, useLanguage } from "@/contexts/LanguageContext";
import { api } from "@/lib/api";

type AuthMeResponse = {
  onboarding_completed: boolean;
};

export default function OnboardingLanguagePage() {
  const router = useRouter();
  const { accessToken, isHydrated } = useAuth();
  const { language, setLanguage } = useLanguage();
  const [selectedLanguage, setSelectedLanguage] = useState(language || "en");

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      router.replace("/auth-options");
    }
  }, [accessToken, isHydrated, router]);

  useEffect(() => {
    if (!accessToken) return;
    api
      .get<AuthMeResponse>("/api/auth/me")
      .then(({ data }) => {
        if (data?.onboarding_completed) {
          router.replace("/main-page");
        }
      })
      .catch(() => {});
  }, [accessToken, router]);

  const canContinue = useMemo(() => Boolean(selectedLanguage), [selectedLanguage]);

  function handleContinue() {
    if (!canContinue) return;
    setLanguage(selectedLanguage);
    sessionStorage.setItem("farmly_onboarding_language", selectedLanguage);
    router.push("/onboarding/farming");
  }

  if (!isHydrated) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-green-100 px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center sm:mb-8">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-green-500 sm:h-20 sm:w-20">
            <Globe className="h-8 w-8 text-white sm:h-10 sm:w-10" />
          </div>
          <h1 className="text-2xl font-bold text-green-800 sm:text-3xl">Choose Language</h1>
          <p className="mt-2 text-sm text-green-700 sm:text-base">
            Select your preferred language for Farmly.
          </p>
        </div>

        <Card className="rounded-2xl border-2 border-green-100 shadow-lg">
          <CardHeader>
            <CardTitle className="text-center text-green-700">Language Selection</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {SUPPORTED_LANGUAGES.map((item) => (
              <button
                type="button"
                key={item.code}
                onClick={() => setSelectedLanguage(item.code)}
                className={`flex w-full items-center justify-between rounded-xl border p-4 text-left transition ${
                  selectedLanguage === item.code
                    ? "border-green-500 bg-green-500 text-white"
                    : "border-green-200 bg-white text-green-800 hover:bg-green-50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold">{item.tag}</span>
                  <span className="font-medium">{item.name}</span>
                </div>
                {selectedLanguage === item.code ? <CheckCircle className="h-5 w-5" /> : null}
              </button>
            ))}

            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/onboarding/location")}
                className="border-green-200 text-green-700 hover:bg-green-50"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button
                type="button"
                onClick={handleContinue}
                disabled={!canContinue}
                className="bg-green-500 text-white hover:bg-green-600"
              >
                Continue
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
