interface ErrorAlertProps {
  title?: string;
  message: string;
}

export function ErrorAlert({ title = "Something went wrong", message }: ErrorAlertProps) {
  return (
    <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-rose-200">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-rose-100/80">{message}</p>
    </div>
  );
}
