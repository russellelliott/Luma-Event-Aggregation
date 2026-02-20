import React from 'react';

const MatchSlider = ({ minMatch, setMinMatch, range = { min: 0, max: 100 } }) => {
  const { min, max } = range;
  
  return (
    <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-2">
        <label className="text-xs font-semibold text-gray-800">
          Min Match Percentage
        </label>
        <span className="text-xs font-bold text-indigo-600">
          {minMatch}%
        </span>
      </div>
      
      <input
        type="range"
        min={min}
        max={max}
        step="1"
        value={minMatch}
        onChange={(e) => setMinMatch(parseInt(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
      />
      
      <div className="flex justify-between text-[10px] text-gray-500 mt-1 font-medium">
        <span>{min}%</span>
        <span>{max}%</span>
      </div>
    </div>
  );
};

export default MatchSlider;
