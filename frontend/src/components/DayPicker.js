import React from 'react';
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
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-gray-800">Days</h3>
        </div>
        <div className="flex gap-1">
          <button
            onClick={selectAll}
            className="text-[10px] font-medium text-indigo-600 hover:bg-indigo-50 px-1.5 py-0.5 rounded transition-colors"
          >
            All
          </button>
          <button
            onClick={clearAll}
            className="text-[10px] font-medium text-gray-500 hover:bg-gray-50 px-1.5 py-0.5 rounded transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1">
        {days.map(day => (
          <button
            key={day.id}
            onClick={() => toggleDay(day.id)}
            className={`
              h-8 w-full rounded-md font-semibold text-xs transition-all duration-150 flex items-center justify-center
              ${selectedDays.has(day.id)
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
              }
            `}
            title={day.full}
          >
            {day.label.charAt(0)}
          </button>
        ))}
      </div>
    </div>
  );
}