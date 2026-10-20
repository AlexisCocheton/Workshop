// Cadre commun à tous les blocs du dashboard.
export default function Card({ title, children }) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-epsi-ink/5">
      <h2 className="mb-4 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}
