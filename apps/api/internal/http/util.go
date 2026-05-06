package http

import "strconv"

// fmtSscan is a tiny shim around strconv.Atoi to avoid pulling fmt into hot
// paths. It returns (n, err) compatible with fmt.Sscan.
func fmtSscan(s string, out *int) (int, error) {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0, err
	}
	*out = n
	return 1, nil
}
