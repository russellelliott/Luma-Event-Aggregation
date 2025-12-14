import React, { useState } from 'react';
import { Calendar } from 'lucide-react';

export default function DayPicker({ selectedDays, onDaysChange }) {
  const days = [
    { id: 'mon', label: 'Mon', full: 'Monday' },
    { id: 'tue', label: 'Tue', full: 'Tuesday' },
    { id: 'wed', label: 'Wed', full: 'Wednesday' },
    { id: 'thu', label: 'Thu', full: 'Thursday' },
    { id: 'fri', label: 'Fri', full: 'Friday' },
    { id: 'sat', label: 'Sat', full: 'Saturday' },
    { id: 'sun', label: 'Sun', full: 'Sunday' }
  ];

  const toggleDay = (dayId) => {
    const newSelected = new Set(selectedDays);
    if (newSelected.has(dayId)) {
      newSelected.delete(dayId);
    } else {
      newSelected.add(dayId);
    }
    onDaysChange(newSelected);
  };

  const selectAll = () => {
    onDaysChange(new Set(days.map(d => d.id)));
  };

  const clearAll = () => {
    onDaysChange(new Set());
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="w-5 h-5 text-indigo-600" />
        <h3 className="text-lg font-semibold text-gray-800">Select Days</h3>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-4">
        {days.map(day => (
          <button
            key={day.id}
            onClick={() => toggleDay(day.id)}
            className={`
              aspect-square rounded-lg font-semibold text-xs transition-all duration-200 flex items-center justify-center
              ${selectedDays.has(day.id)
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
              }
            `}
            title={day.full}
          >
            {day.label}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={selectAll}
          className="flex-1 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-100 transition-colors"
        >
          All
        </button>
        <button
          onClick={clearAll}
          className="flex-1 px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  );
}