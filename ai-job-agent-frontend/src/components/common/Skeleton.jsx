export const Skeleton = ({ className = "" }) => (
  <div className={`animate-pulse rounded-md bg-slate-200 ${className}`} />
);

export const CardSkeleton = () => (
  <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
    <Skeleton className="h-4 w-1/3" />
    <Skeleton className="mt-4 h-8 w-2/3" />
    <Skeleton className="mt-5 h-2 w-full" />
  </div>
);
