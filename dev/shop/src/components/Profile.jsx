import { useEffect, useState } from "react";
import ProfileForm from "./ProfileForm.jsx";
import PasswordForm from "./PasswordForm.jsx";
import { fetchProfile } from "../api.js";

// Page « Mon profil » : informations personnelles et mot de passe du client connecté.
export default function Profile({ session, onExpired, onNameChange }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchProfile(session.token)
      .then(setProfile)
      .catch((e) => (e.status === 401 ? onExpired() : setError(e.message)));
  }, [session.token]);

  if (error) return <p className="rounded-xl bg-white p-6 shadow-sm">Profil indisponible ({error}).</p>;
  if (profile === null) return <p className="p-6">Chargement de votre profil…</p>;

  return (
    <section aria-label="Mon profil" className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-lg font-bold">Mon profil</h2>
      <ProfileForm
        session={session}
        profile={profile}
        onExpired={onExpired}
        onSaved={(saved) => {
          setProfile(saved);
          onNameChange(saved.name);
        }}
      />
      <PasswordForm session={session} onExpired={onExpired} />
    </section>
  );
}
