import React, { useState } from 'react';
import { Calendar, X } from 'lucide-react';

export default function MultiDayCalendar({ selectedDates, onDatesChange }) {
  const [currentDate, setCurrentDate] = useState(new Date());

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    return new Date(year, month, 1).getDay();
  };

  const isSameDay = (d1, d2) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  const isSelected = (day) => {
    const checkDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
    return selectedDates.some(d => 
      d.getFullYear() === checkDate.getFullYear() &&
      d.getMonth() === checkDate.getMonth() &&
      d.getDate() === checkDate.getDate()
    );
  };

  const toggleDate = (day) => {
    const clickedDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
    
    if (isSelected(day)) {
      onDatesChange(selectedDates.filter(d => !isSameDay(d, clickedDate)));
    } else {
      onDatesChange([...selectedDates, clickedDate]);
    }
  };

  const removeDate = (dateToRemove) => {
    onDatesChange(selectedDates.filter(d => !isSameDay(d, dateToRemove)));
  };

  const clearAll = () => {
    onDatesChange([]);
  };

  const previousMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1));
  };

  const formatDate = (date) => {
    return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
  };

  const renderCalendar = () => {
    const daysInMonth = getDaysInMonth(currentDate);
    const firstDay = getFirstDayOfMonth(currentDate);
    const days = [];
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth();

    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="h-12"></div>);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const dayDate = new Date(currentYear, currentMonth, day);
      const selected = selectedDates.some(d => 
        d.getFullYear() === dayDate.getFullYear() &&
        d.getMonth() === dayDate.getMonth() &&
        d.getDate() === dayDate.getDate()
      );
      
      days.push(
        <button
          key={`${currentYear}-${currentMonth}-${day}`}
          onClick={() => toggleDate(day)}
          className={`h-12 rounded-lg font-medium transition-all hover:bg-blue-50 
            ${selected ? 'bg-blue-500 text-white hover:bg-blue-600' : 'text-gray-700'}`}
        >
          {day}
        </button>
      );
    }

    return days;
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white">
      <div className="flex items-center gap-3 mb-6">
        <Calendar className="w-6 h-6 text-blue-500" />
        <h1 className="text-2xl font-bold text-gray-800">Select Multiple Days</h1>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={previousMonth}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            ← Prev
          </button>
          <h2 className="text-xl font-semibold text-gray-800">
            {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
          </h2>
          <button
            onClick={nextMonth}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Next →
          </button>
        </div>

        <div className="grid grid-cols-7 gap-2 mb-2">
          {dayNames.map(day => (
            <div key={day} className="h-10 flex items-center justify-center text-sm font-semibold text-gray-600">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-2">
          {renderCalendar()}
        </div>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800">
            Selected Dates ({selectedDates.length})
          </h3>
          {selectedDates.length > 0 && (
            <button
              onClick={clearAll}
              className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              Clear All
            </button>
          )}
        </div>

        {selectedDates.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No dates selected. Click on calendar days to select them.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {selectedDates
              .sort((a, b) => a - b)
              .map((date, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 bg-blue-100 text-blue-800 px-3 py-2 rounded-lg text-sm"
                >
                  <span>{formatDate(date)}</span>
                  <button
                    onClick={() => removeDate(date)}
                    className="hover:bg-blue-200 rounded p-0.5 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}