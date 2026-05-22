"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type LanguageCode = "en" | "am";
type SupportedLanguage = {
  code: LanguageCode;
  tag: "US" | "ET";
  name: string;
};

type LanguageContextValue = {
  language: LanguageCode;
  setLanguage: (next: LanguageCode) => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);
export const SUPPORTED_LANGUAGES: SupportedLanguage[] = [
  { code: "en", tag: "US", name: "English" },
  { code: "am", tag: "ET", name: "Amharic" },
];

type LanguageProviderProps = {
  children: ReactNode;
};

export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguage] = useState<LanguageCode>(() => {
    if (typeof window === "undefined") return "en";
    const saved = localStorage.getItem("farmly_language");
    if (saved === "en" || saved === "am") {
      return saved as LanguageCode;
    }
    return "en";
  });

  const value = useMemo(
    () => ({
      language,
      setLanguage: (next: LanguageCode) => {
        localStorage.setItem("farmly_language", next);
        setLanguage(next);
      },
    }),
    [language]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used inside LanguageProvider");
  return ctx;
}
