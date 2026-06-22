import { useToastStore } from "../../store/toastStore";

const palette = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  danger: "border-red-200 bg-red-50 text-red-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  info: "border-blue-200 bg-blue-50 text-blue-800",
};

const ToastViewport = () => {
  const { toasts, removeToast } = useToastStore();
  return (
    <div className="fixed right-4 top-4 z-50 flex w-80 flex-col gap-3">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          className={`rounded-lg border px-4 py-3 text-left text-sm shadow-sm ${palette[toast.type] || palette.info}`}
          onClick={() => removeToast(toast.id)}
        >
          {toast.message}
        </button>
      ))}
    </div>
  );
};

export default ToastViewport;
