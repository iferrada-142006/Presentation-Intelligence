import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import HomePage from './pages/HomePage'
import ReportPage from './pages/ReportPage'
import DashboardPage from './pages/DashboardPage'
import HistoryPage from './pages/HistoryPage'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/report/:id" element={<ReportPage />} />
        <Route path="/dashboard/:id" element={<DashboardPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
