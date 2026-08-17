import { formatLottoNumber } from "../../../shared/lottoUtils";

export default function LottoBall({ number, special = false, size = "md" }: { number: number; special?: boolean; size?: "sm" | "md" | "lg" }) {
  const sizeClasses = {
    sm: "h-8 w-8 text-xs",
    md: "h-10 w-10 text-sm",
    lg: "h-12 w-12 text-base",
  };
  return (
    <span className={`lotto-ball ${special ? "lotto-ball-special" : ""} ${sizeClasses[size]}`} aria-label={`${special ? "特別號" : "號碼"} ${number}`}>
      {formatLottoNumber(number)}
    </span>
  );
}
