import { useEffect, useRef } from "react";

/** Opens an accessible native modal while its owning React state is true. */
export function useNativeDialog(open: boolean) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !open || dialog.open) return;

    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [open]);

  return dialogRef;
}
