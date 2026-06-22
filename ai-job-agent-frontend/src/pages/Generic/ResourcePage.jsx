import { useState } from "react";
import { listResource } from "../../api/resources";
import EmptyState from "../../components/common/EmptyState";
import Pagination from "../../components/common/Pagination";
import { CardSkeleton } from "../../components/common/Skeleton";
import { useAsync } from "../../hooks/useAsync";

const pickItems = (data) =>
  data?.items ||
  data?.jobs ||
  data?.resumes ||
  data?.applications ||
  data?.cover_letters ||
  data?.history ||
  data?.matches ||
  data?.reports ||
  data?.events ||
  data?.users ||
  data?.pipelines ||
  data?.runs ||
  [];

const valueFor = (item, keys) => keys.map((key) => item?.[key]).find((value) => value !== undefined && value !== null && value !== "") || "Not available";

const ResourcePage = ({ title, description, endpoint, params = {}, columns, emptyText, admin = false }) => {
  const [page, setPage] = useState(1);
  const { data, loading, error } = useAsync(() => listResource(endpoint, { page, page_size: 20, ...params }), [endpoint, page]);
  const items = pickItems(data);

  if (error?.response?.status === 403 || (admin && error)) {
    return <EmptyState title="Access restricted" description="This area is available only to admin users. The server will grant access when your account has permission." />;
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      {loading ? (
        <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
      ) : items.length ? (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>{columns.map((col) => <th key={col.label} className="px-4 py-3">{col.label}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item, index) => (
                  <tr key={item._id || item.id || index}>
                    {columns.map((col) => {
                      const value = col.render ? col.render(item) : valueFor(item, col.keys);
                      return <td key={col.label} className="px-4 py-3 text-slate-600">{value}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data?.total || 0) > 20 && <Pagination page={page} total={data.total} pageSize={20} onPageChange={setPage} />}
        </div>
      ) : (
        <EmptyState title={`No ${title.toLowerCase()} yet`} description={emptyText} />
      )}
    </div>
  );
};

export default ResourcePage;
