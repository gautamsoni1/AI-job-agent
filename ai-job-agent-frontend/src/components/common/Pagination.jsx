const Pagination = ({ page = 1, total = 0, pageSize = 20, onPageChange }) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-1 pt-4 text-sm">
      <span className="text-slate-500">Page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className="rounded-md border border-slate-200 px-3 py-2" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </button>
        <button className="rounded-md border border-slate-200 px-3 py-2" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
};

export default Pagination;
