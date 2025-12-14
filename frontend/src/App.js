import React, { useState, useEffect } from 'react';
import DistanceSlider from './components/DistanceSlider';
import ClassificationFilter from './components/ClassificationFilter';
import MultiDayCalendar from './components/MultiDayCalendar';
import DayPicker from './components/DayPicker';
import EventCard from './components/EventCard';
import './App.css';

function App() {
  const [cities, setCities] = useState([]);
  const [selectedCityIndex, setSelectedCityIndex] = useState(0);
  const [selectedFilters, setSelectedFilters] = useState({
    eventTypes: [],
    audienceCategories: []
  });
  const [selectedDates, setSelectedDates] = useState([]);
  const [selectedDays, setSelectedDays] = useState(new Set());
  const [events, setEvents] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/cities')
      .then(res => res.json())
      .then(data => {
        setCities(data);
      })
      .catch(err => console.error('Error fetching cities:', err));
  }, []);

  useEffect(() => {
    if (cities.length === 0) return;

    const params = new URLSearchParams();
    
    // Add locations
    const includedCities = cities.slice(0, selectedCityIndex + 1).map(c => c.city.split(',')[0]);
    includedCities.forEach(city => params.append('location', city));

    // Add event types
    selectedFilters.eventTypes.forEach(type => params.append('event-type', type));

    // Add audience
    selectedFilters.audienceCategories.forEach(audience => params.append('audience', audience));

    // Add dates
    selectedDates.forEach(date => params.append('dates', date.toISOString().split('T')[0]));

    // Add weekdays
    const weekdayMap = {
      'mon': 'Monday',
      'tue': 'Tuesday',
      'wed': 'Wednesday',
      'thu': 'Thursday',
      'fri': 'Friday',
      'sat': 'Saturday',
      'sun': 'Sunday'
    };
    Array.from(selectedDays).forEach(day => {
      if (weekdayMap[day]) {
        params.append('weekdays', weekdayMap[day]);
      }
    });

    fetch(`http://localhost:8000/events?${params.toString()}`)
      .then(res => res.json())
      .then(data => setEvents(data))
      .catch(err => console.error('Error fetching events:', err));

  }, [cities, selectedCityIndex, selectedFilters, selectedDates, selectedDays]);

  const handleFilterChange = (category, values) => {
    setSelectedFilters(prev => ({
      ...prev,
      [category]: values
    }));
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900">Luma Event Aggregation</h1>
          <p className="mt-2 text-gray-600">Find events near you</p>
          <p className="mt-2 text-blue-600 font-medium">Found {events.length} events</p>
        </header>

        <DistanceSlider 
          cities={cities}
          selectedCityIndex={selectedCityIndex}
          onCityChange={setSelectedCityIndex}
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Sidebar - Filters */}
          <div className="lg:col-span-4 space-y-6">
            <ClassificationFilter 
              selectedFilters={selectedFilters}
              onFilterChange={handleFilterChange}
            />
            <DayPicker 
              selectedDays={selectedDays}
              onDaysChange={setSelectedDays}
            />
          </div>
          
          {/* Main Content - Calendar */}
          <div className="lg:col-span-8">
            <MultiDayCalendar 
              selectedDates={selectedDates}
              onDatesChange={setSelectedDates}
            />
          </div>
        </div>

        <div className="mt-12">
          <EventCard events={events} />
        </div>
      </div>
    </div>
  );
}

export default App;
