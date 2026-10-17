import { AnimatePresence, motion } from "framer-motion";
import { useEffect, type ReactNode } from "react";
import { useIsDesktop } from "../lib/useMedia";
import { Icon } from "./Icon";

type Props = {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  label?: string;
  /** Wider dialog on desktop (title details). */
  wide?: boolean;
};

export function Sheet({ open, onClose, title, children, label, wide = false }: Props) {
  const desktop = useIsDesktop();
  // Phones: bottom sheet sliding up. Desktop: centred dialog that fades and scales in.
  const motionProps = desktop
    ? {
        initial: { opacity: 0, scale: 0.96, y: 12 },
        animate: { opacity: 1, scale: 1, y: 0 },
        exit: { opacity: 0, scale: 0.97, y: 8 },
        transition: { duration: 0.18 },
      }
    : {
        initial: { y: "100%" },
        animate: { y: 0 },
        exit: { y: "100%" },
        transition: { type: "spring" as const, damping: 32, stiffness: 340 },
      };
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="sheet-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className={`sheet${wide ? " wide" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-label={label ?? (typeof title === "string" ? title : "Details")}
            {...motionProps}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sheet-grip" />
            {title !== undefined && (
              <div className="sheet-head">
                <div className="h2">{title}</div>
                <button className="icon-btn" onClick={onClose} aria-label="Close">
                  <Icon name="x" size={18} />
                </button>
              </div>
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
