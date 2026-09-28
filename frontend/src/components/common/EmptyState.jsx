export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="text-center py-12">
      {Icon && <Icon className="w-16 h-16 text-slate-600 mx-auto mb-4" />}
      <h3 className="text-lg font-semibold text-slate-400 mb-2">{title}</h3>
      {description && <p className="text-slate-500 mb-4">{description}</p>}
      {action}
    </div>
  );
}
