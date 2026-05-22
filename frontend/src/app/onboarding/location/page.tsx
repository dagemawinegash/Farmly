"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle, Globe, Loader2, MapPin, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

type LocationData = {
  latitude: number;
  longitude: number;
  accuracy: number;
  address?: string;
};

type PhotonFeature = {
  properties?: {
    name?: string;
    country?: string;
  };
  geometry: {
    coordinates: [number, number];
  };
};

type AuthMeResponse = {
  onboarding_completed: boolean;
};

function toLocationString(locationData: LocationData) {
  return `${locationData.latitude.toFixed(6)},${locationData.longitude.toFixed(6)}`;
}

export default function OnboardingLocationPage() {
  const router = useRouter();
  const { accessToken, isHydrated } = useAuth();

  const [isDetecting, setIsDetecting] = useState(false);
  const [locationData, setLocationData] = useState<LocationData | null>(null);
  const [error, setError] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PhotonFeature[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const isMobile =
    typeof navigator !== "undefined" &&
    /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(
      (navigator.userAgent || navigator.vendor || "").toLowerCase()
    );

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

  function persistLocation(nextLocation: LocationData) {
    setLocationData(nextLocation);
    sessionStorage.setItem("farmly_onboarding_location", JSON.stringify(nextLocation));
    sessionStorage.setItem("farmly_onboarding_location_string", toLocationString(nextLocation));
    setTimeout(() => router.push("/onboarding/language"), 900);
  }

  function detectLocation() {
    setIsDetecting(true);
    setError("");
    setShowManualInput(false);

    if (!navigator.geolocation) {
      setError("Geolocation is not supported by this browser.");
      setIsDetecting(false);
      setShowManualInput(true);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        persistLocation({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        });
        setIsDetecting(false);
      },
      (geoError) => {
        let message = "Unable to retrieve your location.";
        if (geoError.code === geoError.PERMISSION_DENIED) {
          message = "Location access denied. Please allow location access or enter manually.";
        } else if (geoError.code === geoError.TIMEOUT) {
          message = "Location request timed out. Please try again or enter manually.";
        }
        setError(message);
        setIsDetecting(false);
        setShowManualInput(true);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 120000,
      }
    );
  }

  async function searchLocation(query: string) {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    setIsSearching(true);
    try {
      const response = await fetch(`https://photon.komoot.io/api/?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      const features: PhotonFeature[] = Array.isArray(data?.features) ? data.features.slice(0, 5) : [];
      setSearchResults(features);
    } catch {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }

  function handleSearchInput(value: string) {
    setSearchQuery(value);
    searchLocation(value);
  }

  function selectLocation(feature: PhotonFeature) {
    const [longitude, latitude] = feature.geometry.coordinates || [];
    if (typeof latitude !== "number" || typeof longitude !== "number") return;

    persistLocation({
      latitude,
      longitude,
      accuracy: 100,
      address: `${feature.properties?.name || ""}, ${feature.properties?.country || ""}`.trim(),
    });
  }

  if (!isHydrated) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-green-100 px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center sm:mb-8">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-green-500 sm:h-20 sm:w-20">
            <MapPin className="h-8 w-8 text-white sm:h-10 sm:w-10" />
          </div>
          <h1 className="text-2xl font-bold text-green-800 sm:text-3xl">Location Required</h1>
          <p className="mt-2 text-sm text-green-700 sm:text-base">
            We use your location to provide local farming recommendations.
          </p>
        </div>

        <Card className="rounded-2xl border-2 border-green-100 shadow-lg">
          <CardHeader>
            <CardTitle className="text-center text-green-700">
              {isMobile ? "Enable Location Access" : "Location Detection"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!isMobile && (
              <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
                Desktop may be less accurate. You can still enter location manually.
              </div>
            )}

            {isDetecting && (
              <div className="py-8 text-center">
                <Loader2 className="mx-auto h-8 w-8 animate-spin text-green-600" />
                <p className="mt-3 text-sm text-green-700">Detecting your location...</p>
              </div>
            )}

            {locationData && (
              <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800">
                <div className="mb-2 flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-700" />
                  <span className="font-medium">Location saved</span>
                </div>
                <p>Latitude: {locationData.latitude.toFixed(6)}</p>
                <p>Longitude: {locationData.longitude.toFixed(6)}</p>
                {locationData.address ? <p>Address: {locationData.address}</p> : null}
                <p className="mt-2 text-xs">Continuing to language selection...</p>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <div className="mb-1 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium">Location Error</span>
                </div>
                <p>{error}</p>
              </div>
            )}

            {showManualInput && (
              <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
                <p className="text-sm font-medium text-blue-800">Enter location manually</p>
                <div className="relative">
                  <Input
                    placeholder="Search city or area (example: Addis Ababa)"
                    value={searchQuery}
                    onChange={(e) => handleSearchInput(e.target.value)}
                    className="pr-10"
                  />
                  {isSearching ? (
                    <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin text-blue-500" />
                  ) : (
                    <Search className="absolute right-3 top-3 h-4 w-4 text-blue-500" />
                  )}
                </div>
                {searchResults.length > 0 && (
                  <div className="max-h-44 space-y-2 overflow-y-auto">
                    {searchResults.map((item, index) => (
                      <button
                        type="button"
                        key={`${item.properties?.name || "result"}-${index}`}
                        onClick={() => selectLocation(item)}
                        className="w-full rounded-lg border border-blue-100 bg-white p-3 text-left text-sm hover:bg-blue-50"
                      >
                        <p className="font-medium text-blue-900">{item.properties?.name || "Unknown"}</p>
                        <p className="text-xs text-blue-700">{item.properties?.country || ""}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!isDetecting && !locationData && (
              <div className="space-y-3">
                <Button
                  type="button"
                  onClick={detectLocation}
                  className="w-full bg-green-500 py-3 font-semibold text-white hover:bg-green-600"
                >
                  <MapPin className="mr-2 h-4 w-4" />
                  Detect My Location
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowManualInput((v) => !v)}
                  className="w-full border-green-200 text-green-700 hover:bg-green-50"
                >
                  <Globe className="mr-2 h-4 w-4" />
                  Enter Location Manually
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
