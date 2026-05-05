import { useEffect } from "react";

export default function App() {
  useEffect(() => {
    window.location.replace("/api/app");
  }, []);

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      height: "100vh",
      background: "#0f0f0f",
      color: "#fff",
      fontFamily: "sans-serif",
      fontSize: "1rem"
    }}>
      MAGO Emergency 로딩 중...
    </div>
  );
}
