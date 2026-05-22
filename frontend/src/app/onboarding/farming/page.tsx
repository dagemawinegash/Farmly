"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, ChevronDown, Plus, User, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { api } from "@/lib/api";
import type { AxiosError } from "axios";

const USER_TYPE_OPTIONS = [
  { value: "aspiring", label: "Aspiring farmer" },
  { value: "beginner", label: "Beginner farmer" },
  { value: "experienced", label: "Experienced farmer" },
  { value: "explorer", label: "Explorer" },
];

const MAIN_GOAL_OPTIONS = [
  { value: "increase_yield", label: "Increase crop yield" },
  { value: "reduce_costs", label: "Reduce farming costs" },
  { value: "sustainable_farming", label: "Sustainable farming" },
  { value: "organic_farming", label: "Organic farming" },
  { value: "market_access", label: "Better market access" },
];

type ProfileResponse = {
  full_name: string | null;
  phone_number: string | null;
  location: string | null;
  preferred_language: string | null;
};

type OnboardingFormData = {
  full_name: string;
  phone_number: string;
  preferred_language: string;
  user_type: string;
  years_experience: string;
  main_goal: string;
  crops_grown: string[];
};

type SelectFieldProps = {
  id: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
};

function SelectField({ id, value, onChange, children }: SelectFieldProps) {
  return (
    <div className="relative max-w-[260px]">
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full appearance-none rounded-xl border border-green-300 bg-white px-4 pr-10 text-sm text-green-900 outline-none transition-all duration-200 ease-out focus:border-green-500 focus:ring-2 focus:ring-green-200"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-green-500 transition-transform duration-200" />
    </div>
  );
}

function errorMessageFrom(error: unknown) {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return (
    axiosError?.response?.data?.detail ||
    axiosError?.message ||
    "Failed to complete onboarding. Please try again."
  );
}

export default function OnboardingFarmingPage() {
  const router = useRouter();
  const { accessToken, isHydrated } = useAuth();
  const { language } = useLanguage();

  const [isLoading, setIsLoading] = useState(false);
  const [isPrefilling, setIsPrefilling] = useState(true);
  const [error, setError] = useState("");

  const [locationString, setLocationString] = useState(() => {
    if (typeof window === "undefined") return "";
    return sessionStorage.getItem("farmly_onboarding_location_string") || "";
  });
  const [cropInput, setCropInput] = useState("");
  const [formData, setFormData] = useState<OnboardingFormData>({
    full_name: "",
    phone_number: "",
    preferred_language:
      typeof window !== "undefined"
        ? sessionStorage.getItem("farmly_onboarding_language") || "en"
        : "en",
    user_type: "",
    years_experience: "0",
    main_goal: "",
    crops_grown: [],
  });

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      router.replace("/auth-options");
    }
  }, [accessToken, isHydrated, router]);

  useEffect(() => {
    if (!isHydrated || !accessToken) return;

    api
      .get<ProfileResponse>("/api/users/me/profile")
      .then(({ data }) => {
        if (!locationString.trim() && data?.location) {
          setLocationString(data.location);
        }
        setFormData((prev) => ({
          ...prev,
          full_name: data?.full_name || prev.full_name,
          phone_number: data?.phone_number || prev.phone_number,
          preferred_language: data?.preferred_language || prev.preferred_language || language || "en",
        }));
      })
      .catch(() => {})
      .finally(() => setIsPrefilling(false));
  }, [accessToken, isHydrated, language, locationString, router]);

  useEffect(() => {
    if (!isHydrated || isPrefilling) return;
    if (!locationString.trim()) {
      router.replace("/onboarding/location");
    }
  }, [isHydrated, isPrefilling, locationString, router]);

  function addCrop() {
    const normalized = cropInput.trim().toLowerCase();
    if (!normalized) return;
    setFormData((prev) => {
      if (prev.crops_grown.includes(normalized)) return prev;
      return {
        ...prev,
        crops_grown: [...prev.crops_grown, normalized],
      };
    });
    setCropInput("");
  }

  function removeCrop(crop: string) {
    setFormData((prev) => ({
      ...prev,
      crops_grown: prev.crops_grown.filter((item) => item !== crop),
    }));
  }

  const formIsValid = useMemo(() => {
    return (
      formData.full_name.trim().length >= 2 &&
      locationString.trim().length >= 2 &&
      formData.preferred_language.trim().length >= 2 &&
      formData.user_type &&
      formData.main_goal &&
      formData.crops_grown.length >= 1 &&
      Number(formData.years_experience) >= 0 &&
      Number(formData.years_experience) <= 80
    );
  }, [formData, locationString]);

  async function handleSubmit() {
    const missingFields: string[] = [];
    if (!formData.full_name.trim()) missingFields.push("account name");
    if (!locationString.trim()) missingFields.push("location");
    if (!formData.preferred_language.trim()) missingFields.push("preferred language");
    if (!formData.user_type) missingFields.push("farming experience");
    if (!formData.years_experience.trim()) missingFields.push("years of experience");
    if (!formData.main_goal) missingFields.push("main goal");
    if (formData.crops_grown.length < 1) missingFields.push("at least one crop");

    if (missingFields.length > 0 || !formIsValid) {
      setError(`Please complete: ${missingFields.join(", ")}.`);
      return;
    }

    setError("");
    setIsLoading(true);
    try {
      await api.post("/api/onboarding/complete", {
        full_name: formData.full_name.trim(),
        phone_number: formData.phone_number.trim() || null,
        location: locationString.trim(),
        preferred_language: formData.preferred_language,
        user_type: formData.user_type,
        years_experience: Number(formData.years_experience),
        main_goal: formData.main_goal,
        crops_grown: formData.crops_grown,
      });

      sessionStorage.removeItem("farmly_onboarding_location");
      sessionStorage.removeItem("farmly_onboarding_location_string");
      sessionStorage.removeItem("farmly_onboarding_language");
      router.push("/main-page");
    } catch (submitError: unknown) {
      setError(errorMessageFrom(submitError));
    } finally {
      setIsLoading(false);
    }
  }

  if (!isHydrated || isPrefilling) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-green-100 px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center sm:mb-8">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-green-500 sm:h-20 sm:w-20">
            <User className="h-8 w-8 text-white sm:h-10 sm:w-10" />
          </div>
          <h1 className="text-2xl font-bold text-green-800 sm:text-3xl">Tell Us About Your Farming</h1>
          <p className="mt-2 text-sm text-green-700 sm:text-base">
            This helps us personalize recommendations for you.
          </p>
        </div>

        <Card className="rounded-2xl border-2 border-green-100 shadow-lg">
          <CardContent className="space-y-4 p-5 sm:p-6">
            <div className="space-y-2">
              <Label htmlFor="preferred_language">Preferred Language</Label>
              <SelectField
                id="preferred_language"
                value={formData.preferred_language}
                onChange={(value) =>
                  setFormData((prev) => ({ ...prev, preferred_language: value }))
                }
              >
                <option value="en">English</option>
                <option value="am">Amharic</option>
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="user_type">Farming Experience</Label>
              <SelectField
                id="user_type"
                value={formData.user_type}
                onChange={(value) => setFormData((prev) => ({ ...prev, user_type: value }))}
              >
                <option value="">Farming Experience</option>
                {USER_TYPE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="years_experience">Years of Experience</Label>
              <SelectField
                id="years_experience"
                value={formData.years_experience}
                onChange={(value) => setFormData((prev) => ({ ...prev, years_experience: value }))}
              >
                <option value="">Please select years of experience</option>
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30].map((years) => (
                  <option key={years} value={years.toString()}>
                    {years} {years === 1 ? "year" : "years"}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="main_goal">Main Goal</Label>
              <SelectField
                id="main_goal"
                value={formData.main_goal}
                onChange={(value) => setFormData((prev) => ({ ...prev, main_goal: value }))}
              >
                <option value="">Main Goal</option>
                {MAIN_GOAL_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-3">
              <Label>Crops Grown</Label>
              <div className="flex gap-2">
                <Input
                  value={cropInput}
                  onChange={(e) => setCropInput(e.target.value)}
                  placeholder="Add crop (example: maize)"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCrop();
                    }
                  }}
                />
                <Button
                  type="button"
                  onClick={addCrop}
                  className="bg-green-500 text-white hover:bg-green-600"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {formData.crops_grown.length > 0 ? (
                <div className="space-y-2">
                  {formData.crops_grown.map((crop) => (
                    <div
                      key={crop}
                      className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm"
                    >
                      <span className="font-medium text-green-800">{crop}</span>
                      <button
                        type="button"
                        onClick={() => removeCrop(crop)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted">Add at least one crop.</p>
              )}
            </div>

            {error ? (
              <div className="rounded-[var(--radius)] border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-4 pt-2 sm:grid-cols-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/onboarding/language")}
                className="h-12 rounded-2xl border-green-200 bg-white text-base font-semibold text-green-700 transition-all duration-200 hover:-translate-y-0.5 hover:bg-green-50"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={isLoading}
                className="h-12 rounded-2xl bg-green-500 px-5 text-base font-semibold text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-green-600"
              >
                {isLoading ? "Saving..." : "Complete Onboarding"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
