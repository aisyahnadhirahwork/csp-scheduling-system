document.addEventListener('alpine:init', () => {
  Alpine.data('appointments', () => ({
    selected: 'upcoming',
    rows: [],  // will hold fetched appointments

    async init() {
      // fetch appointments from Django backend
      try {
        const res = await fetch('/api/appointments/');
        const data = await res.json();
        this.rows = data;  // store in Alpine reactive property
      } catch (err) {
        console.error('Error fetching appointments:', err);
      }
    },

    get tableContent() {
      // filter by tab
      const filtered = this.rows.filter(a => {
        if (this.selected === 'upcoming') return a.status === 'Upcoming';
        if (this.selected === 'completed') return a.status === 'Completed';
        if (this.selected === 'cancelled') return a.status === 'Cancelled';
      });

      // return HTML for table rows
      return filtered.map(a => `
        <tr>
          <td class="px-5 py-4 sm:px-6">
            <div class="text-gray-800 dark:text-white/90">${a.name}</div>
          </td>
          <td class="px-5 py-4 sm:px-6">
            <div class="text-gray-500 dark:text-gray-400">${a.status}</div>
          </td>
        </tr>
      `).join('');
    },
  }));
});
