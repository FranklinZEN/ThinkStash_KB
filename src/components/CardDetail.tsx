const fetchCard = async () => {
  try {
    const response = await fetch(`/api/cards/${cardId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch card');
    }
    const data = await response.json();
    setCard(data);
  } catch (error) {
    console.error('Error fetching card:', error);
    setError('Failed to load card details');
  }
}; 