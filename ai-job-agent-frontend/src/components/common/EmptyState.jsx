const EmptyState = ({ title, description, action }) => (
  <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
    <div className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-slate-100 text-slate-500">+</div>
    <h3 className="mt-4 text-base font-semibold text-slate-950">{title}</h3>
    <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{description}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>
);

export default EmptyState;
