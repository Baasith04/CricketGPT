/**
 * SettingsCard.jsx
 * Reusable glass card container used for every section on the Account page.
 */

export default function SettingsCard({ title, description, children }) {
  return (
    <div
      className="bg-primary-dark/75 backdrop-blur-xl border border-white/15
                 rounded-2xl shadow-xl shadow-blue-950/40 overflow-hidden"
    >
      {/* Card header */}
      <div className="px-5 sm:px-7 py-4 sm:py-5 border-b border-white/10">
        <h2 className="text-white font-bold text-base sm:text-lg">{title}</h2>
        {description && (
          <p className="text-blue-100/55 text-xs sm:text-sm mt-0.5">{description}</p>
        )}
      </div>

      {/* Card body */}
      <div className="px-5 sm:px-7 py-5 sm:py-6">{children}</div>
    </div>
  );
}
