import React from 'react';

const MatchSlider = ({ maxDistance, setMaxDistance, range = { min: 0.0, max: 2.0 } }) => {
  const { min, max } = range;
  // Default bounds if range is invalid
  const minVal = min || 0;
  const maxVal = max || 2.0;
  
  return (
    <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-2">
        <label className="text-xs font-semibold text-gray-800">
          Max Cosine Distance
        </label>
        <span className="text-xs font-bold text-indigo-600">
          {typeof maxDistance === 'number' ? maxDistance.toFixed(2) : 'N/A'}
        </span>
      </div>
      
      <input
        type="range"
        min={minVal}
        max={maxVal}
        step="0.01"
        value={maxDistance}
        onChange={(e) => setMaxDistance(parseFloat(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
      />
      
      <div className="flex justify-between text-[10px] text-gray-500 mt-1 font-medium">
        <span>{minVal.toFixed(2)}</span>
        <span>{maxVal.toFixed(2)}</span>
      </div>
    </div>
  );
};

export default MatchSlider;
