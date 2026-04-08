"use client";

import { useState } from "react";
import { motion } from "framer-motion";

import { CookieBanner } from "@/components/cookie-banner";
import { Header } from "@/components/header";
import { Sidebar } from "@/components/sidebar";
import { pageTransition } from "@/lib/animations";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="dashboard-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="dashboard-main">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <motion.main className="dashboard-content" variants={pageTransition} initial="initial" animate="animate">
          {children}
        </motion.main>
      </div>
      <CookieBanner />
    </div>
  );
}
