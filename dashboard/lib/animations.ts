import { Variants } from "framer-motion";

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.34, 1.56, 0.64, 1] } },
};

export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.04,
    },
  },
};

export const riseIn: Variants = {
  initial: { opacity: 0, y: 18 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: [0.34, 1.56, 0.64, 1] },
  },
};

export const toastSlide: Variants = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, x: 16, transition: { duration: 0.18 } },
};

export const chartReveal: Variants = {
  initial: { opacity: 0, scaleX: 0.94, transformOrigin: "left center" },
  animate: { opacity: 1, scaleX: 1, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
};
