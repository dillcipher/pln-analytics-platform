import { NavLink } from "react-router-dom";

const menuStyle = ({ isActive }: { isActive: boolean }) => ({
  textDecoration: "none",
  color: isActive ? "#14ACE8" : "#D6DCEB",
  padding: "10px 14px",
  borderRadius: "8px",
  background: isActive ? "#162338" : "transparent",
  transition: "0.2s",
  fontWeight: isActive ? 600 : 400,
});

export default function Sidebar() {
  return (
    <aside
      style={{
        background: "#101827",
        borderRight: "1px solid #1d293d",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        height: "100vh",
        width: 260,
        boxSizing: "border-box",
      }}
    >
      <h2
        style={{
          margin: 0,
          color: "#14ACE8",
        }}
      >
        PLN Analytics
      </h2>

      <nav
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          marginTop: 30,
        }}
      >
        <NavLink to="/" style={menuStyle}>
          📊 Executive Dashboard
        </NavLink>

        <NavLink to="/upload" style={menuStyle}>
          ⬆️ Upload Center
        </NavLink>

        <NavLink to="/dlpd" style={menuStyle}>
          ⚡ DLPD Monitoring
        </NavLink>

        <NavLink to="/suspect" style={menuStyle}>
          🔎 Suspect Analytics
        </NavLink>

        <NavLink to="/data-management" style={menuStyle}>
          📁 Data Management
        </NavLink>

        <NavLink to="/settings" style={menuStyle}>
          ⚙ Settings
        </NavLink>
      </nav>
    </aside>
  );
}