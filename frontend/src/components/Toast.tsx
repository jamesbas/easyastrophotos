interface Props {
  message: string;
  kind: "success" | "error";
}

export function Toast({ message, kind }: Props) {
  return <div className={`toast ${kind}`}>{message}</div>;
}
