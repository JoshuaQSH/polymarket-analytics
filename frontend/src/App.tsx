import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { EventDetailPage } from "./pages/EventDetail";
import { EventListPage } from "./pages/EventList";
import { StrategyBenefitsPage } from "./pages/StrategyBenefits";
import { StrategyPage } from "./pages/StrategyPage";

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/" element={<EventListPage />} />
        <Route path="/event/:eventId" element={<EventDetailPage />} />
        <Route path="/strategies" element={<StrategyPage />} />
        <Route path="/strategy-benefits" element={<StrategyBenefitsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
