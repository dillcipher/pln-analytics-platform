import { Outlet } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

export default function MainLayout() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "260px 1fr",
        height: "100vh",
      }}
    >
      <Sidebar />

      <main>
        <Navbar />

        <div
          style={{
            padding: 24,
          }}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}