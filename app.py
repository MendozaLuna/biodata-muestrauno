import { useState, useMemo, useCallback } from "react";
import Navbar from "@/components/Navbar";
import HeroSearch from "@/components/HeroSearch";
import LocationPicker from "@/components/LocationPicker";
import SearchFilters, { type FilterType } from "@/components/SearchFilters";
import ClinicCard from "@/components/ClinicCard";
import ClinicMap from "@/components/ClinicMap";
import { mockClinics } from "@/data/mockData";
import { Eye, Shield, Zap } from "lucide-react";
import { motion } from "framer-motion";

type UserLocation = { lat: number; lng: number; label: string } | null;

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number) {
  const toRad = (v: number) => (v * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const Index = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterType>("rating");
  const [userLocation, setUserLocation] = useState<UserLocation>(null);

  const handleSearch = () => {};

  const filteredClinics = useMemo(() => {
    let clinics = mockClinics;

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      clinics = clinics.filter((c) =>
        c.exams.some(
          (e) =>
            e.name.toLowerCase().includes(q) ||
            e.description.toLowerCase().includes(q) ||
            e.category.toLowerCase().includes(q)
        )
      );
    }

    switch (activeFilter) {
      case "nearest":
        if (userLocation) {
          return [...clinics].sort(
            (a, b) =>
              haversineKm(userLocation.lat, userLocation.lng, a.lat, a.lng) -
              haversineKm(userLocation.lat, userLocation.lng, b.lat, b.lng)
          );
        }
        return clinics;
      case "cheapest":
        return [...clinics].sort((a, b) => {
          const minA = Math.min(...a.exams.map((e) => e.price));
          const minB = Math.min(...b.exams.map((e) => e.price));
          return minA - minB;
        });
      case "rating":
        return [...clinics].sort((a, b) => b.rating - a.rating);
      case "available":
        return clinics.filter((c) => c.exams.some((e) => e.available));
      default:
        return clinics;
    }
  }, [searchQuery, activeFilter, userLocation]);

  const getDistance = useCallback(
    (lat: number, lng: number) =>
      userLocation ? haversineKm(userLocation.lat, userLocation.lng, lat, lng) : null,
    [userLocation]
  );

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <HeroSearch
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearch={handleSearch}
        onExamsDetected={(exams) => {
          // Set search query to first detected exam to filter results
          if (exams.length > 0) {
            setSearchQuery(exams[0]);
          }
        }}
      />

      {/* Location + Results */}
      <section className="container px-4 py-10 max-w-4xl mx-auto">
        <div className="mb-6">
          <LocationPicker userLocation={userLocation} onLocationChange={setUserLocation} />
        </div>
        {/* Map */}
        <div className="mb-6">
          <ClinicMap clinics={filteredClinics} userLocation={userLocation} />
        </div>
        <SearchFilters
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
          resultCount={filteredClinics.length}
        />
        <div className="space-y-4">
          {filteredClinics.map((clinic, i) => (
            <ClinicCard
              key={clinic.id}
              clinic={clinic}
              searchQuery={searchQuery}
              index={i}
              distance={getDistance(clinic.lat, clinic.lng)}
            />
          ))}
          {filteredClinics.length === 0 && (
            <div className="text-center py-16">
              <p className="text-muted-foreground text-lg">No se encontraron centros para esa búsqueda.</p>
              <p className="text-sm text-muted-foreground mt-1">Intenta con otro examen o filtro.</p>
            </div>
          )}
        </div>
      </section>

      {/* Features */}
      <section className="bg-muted/50 py-16 px-4">
        <div className="container max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-foreground text-center mb-10">
             "¿Por qué usar BioData?"
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: <Eye className="h-6 w-6" />,
                title: "Transparencia total",
                desc: "Compara precios y disponibilidad de exámenes en tiempo real.",
              },
              {
                icon: <Zap className="h-6 w-6" />,
                title: "Citas al instante",
                desc: "Contacta directamente por WhatsApp y agenda sin esperas.",
              },
              {
                icon: <Shield className="h-6 w-6" />,
                title: "Centros verificados",
                desc: "Solo clínicas con equipos certificados y profesionales calificados.",
              },
            ].map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15 }}
                className="bg-card rounded-xl p-6 shadow-card text-center"
              >
                <div className="w-12 h-12 rounded-xl gradient-primary flex items-center justify-center text-primary-foreground mx-auto mb-4">
                  {f.icon}
                </div>
                <h3 className="font-semibold text-foreground mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-4">
        <div className="container max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded gradient-primary flex items-center justify-center">
              <Eye className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
            <span className="font-semibold text-sm text-foreground">BioData</span>
          </div>
          <p className="text-xs text-muted-foreground">
             2026 BioData Venezuela. Todos los derechos reservados.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
