import (
	"fmt"

	iotago "github.com/iotaledger/iota.go/v3"
	"github.com/iotaledger/wasp/packages/isc"
	"github.com/iotaledger/wasp/packages/solo"
)

// L1Address matches the struct definition in ISCTypes.sol
type L1Address struct {
	Data []byte
}

func WrapL1Address(a iotago.Address) L1Address {
	if a == nil {
		return L1Address{Data: []byte{}}
	}
	return L1Address{Data: isc.BytesFromAddress(a)}
}

// https://github.com/iotaledger/wasp/blob/develop/packages/vm/core/evm/evmtest/evm_test.go
func TestSendBaseTokens(t *testing.T) {
	env := initEVM(t)

	ethKey, ethAddress := env.soloChain.NewEthereumAccountWithL2Funds()
	_, receiver := env.solo.NewKeyPair()

	fmt.Print(receiver)
	fmt.Print(WrapL1Address(receiver))
}

// TODO: https://wiki.iota.org/shimmer/smart-contracts/guide/solo/what-is-solo