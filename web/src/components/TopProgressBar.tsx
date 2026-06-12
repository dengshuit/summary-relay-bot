import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

export default function TopProgressBar() {
  const location = useLocation();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // On location path changes, spin up the progress animation
    setVisible(true);
    setProgress(15);

    const step1 = setTimeout(() => {
      setProgress(40);
    }, 80);

    const step2 = setTimeout(() => {
      setProgress(75);
    }, 180);

    const step3 = setTimeout(() => {
      setProgress(100);
    }, 320);

    const done = setTimeout(() => {
      setVisible(false);
      setProgress(0);
    }, 550);

    return () => {
      clearTimeout(step1);
      clearTimeout(step2);
      clearTimeout(step3);
      clearTimeout(done);
    };
  }, [location.pathname]);

  if (!visible) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] pointer-events-none h-[3px] bg-transparent">
      {/* Solid brand runner */}
      <div
        className="h-full bg-[#4f46e5] transition-all duration-350 ease-out relative"
        style={{ width: `${progress}%` }}
      >
        {/* Subtle end bead shadow */}
        <span
          className="absolute right-0 top-0 h-full w-[10px] bg-white opacity-90 shadow-[0_0_8px_#4f46e5]"
        />
      </div>
    </div>
  );
}
