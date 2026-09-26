import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { MotionConfig } from "framer-motion";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./app.jsx";
import AuthScreen from "./AuthScreen.jsx";
import { AuthProvider, useAuth } from "./auth.jsx";
import "./index.css";
const Students=lazy(()=>import("./pages/Students.jsx"));
const Batch=lazy(()=>import("./pages/Batch.jsx"));
const Admin=lazy(()=>import("./pages/Admin.jsx"));
const StudentHome=lazy(()=>import("./pages/StudentHome.jsx"));
const IntelligenceServices=lazy(()=>import("./pages/IntelligenceServices.jsx"));
const ServicesHub=lazy(()=>import("./pages/ServicesHub.jsx"));
try{document.documentElement.dataset.theme=localStorage.getItem("gradeai-theme")||"brass"}catch{}
const Splash=()=> <div className="grid min-h-screen place-items-center bg-[var(--bg)] text-sm text-neutral-500">Loading…</div>;
function Gate(){const {user,ready}=useAuth();if(!ready)return <Splash/>;if(!user)return <AuthScreen/>;const staff=user.role==="teacher"||user.role==="admin";return <Suspense fallback={<Splash/>}><Routes><Route path="/" element={<ServicesHub/>}/><Route path="/grade" element={staff?<App/>:<StudentHome/>}/><Route path="/services/:serviceId" element={<IntelligenceServices/>}/><Route path="/intelligence" element={<Navigate to="/services/weather" replace/>}/><Route path="/students" element={staff?<Students/>:<Navigate to="/" replace/>}/><Route path="/batch" element={staff?<Batch/>:<Navigate to="/" replace/>}/><Route path="/admin" element={user.role==="admin"?<Admin/>:<Navigate to="/" replace/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes></Suspense>}
ReactDOM.createRoot(document.getElementById("root")).render(<React.StrictMode><MotionConfig reducedMotion="user"><BrowserRouter><AuthProvider><Gate/></AuthProvider></BrowserRouter></MotionConfig></React.StrictMode>);
