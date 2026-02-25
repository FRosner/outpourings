package counter

import (
	"sync"
	"testing"
)

func TestCounter(t *testing.T) {
	c := Counter{}
	var wg sync.WaitGroup

	for i := 0; i < 1000; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Increment()
		}()
	}

	wg.Wait()

	if c.Value() != 1000 {
		t.Errorf("expected 1000, got %d", c.Value())
	}
}
