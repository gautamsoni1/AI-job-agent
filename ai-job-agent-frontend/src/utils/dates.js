export const formatDate = (value) => {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
};

export const formatRelativeTime = (value) => {
  if (!value) return "Just now";
  const diff = new Date(value).getTime() - Date.now();
  const abs = Math.abs(diff);
  const units = [
    ["day", 86400000],
    ["hour", 3600000],
    ["minute", 60000],
  ];
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const [unit, ms] = units.find(([, size]) => abs >= size) || ["second", 1000];
  return formatter.format(Math.round(diff / ms), unit);
};
