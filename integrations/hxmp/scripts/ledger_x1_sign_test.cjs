const TransportNodeHid =
  require("@ledgerhq/hw-transport-node-hid").default;

const Solana =
  require("@ledgerhq/hw-app-solana").default;

const {
  Connection,
  PublicKey,
  Transaction,
  TransactionInstruction,
} = require("@solana/web3.js");

const RPC = "https://rpc.mainnet.x1.xyz";
const MEMO_PROGRAM =
  new PublicKey("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");

const PATH = "44'/501'/1'/0'";
const EXPECTED =
  "3g8TZbnj6mnTrzS6qm1nkHUNQntrVnPD2f9bjfNpMjeU";

async function main() {
  let transport;

  try {
    console.log("Opening Ledger...");

    transport = await TransportNodeHid.open("");
    const solana = new Solana(transport);

    const result = await solana.getAddress(PATH, false);
    const wallet = new PublicKey(result.address);
    const address = wallet.toBase58();

    console.log("Ledger wallet:", address);

    if (address !== EXPECTED) {
      throw new Error(
        `Wrong Ledger wallet. Expected ${EXPECTED}`
      );
    }

    const connection = new Connection(RPC, "confirmed");
    const { blockhash } =
      await connection.getLatestBlockhash();

    const memo = new TransactionInstruction({
      programId: MEMO_PROGRAM,
      keys: [
        {
          pubkey: wallet,
          isSigner: true,
          isWritable: false,
        },
      ],
      data: Buffer.from(
        "HXMP LEDGER SIGN TEST - DO NOT BROADCAST",
        "utf8"
      ),
    });

    const tx = new Transaction().add(memo);

    tx.feePayer = wallet;
    tx.recentBlockhash = blockhash;

    console.log("");
    console.log("SIGN-ONLY TEST");
    console.log("NO transaction will be broadcast.");
    console.log("Approve the transaction on the Nano X.");

    const signed =
      await solana.signTransaction(
        PATH,
        tx.serializeMessage()
      );

    tx.addSignature(wallet, signed.signature);

    const verified = tx.verifySignatures();

    console.log("");
    console.log("Signature length:", signed.signature.length);
    console.log("Signature verified:", verified);
    console.log("Broadcast attempted: NO");

    if (!verified) {
      throw new Error("Ledger signature did not verify");
    }

    console.log("");
    console.log(
      "SUCCESS: Ledger can sign an HXMP-style X1 memo transaction."
    );
  } finally {
    if (transport) {
      await transport.close();
    }
  }
}

main().catch((err) => {
  console.error("");
  console.error("SIGN TEST FAILED:");
  console.error(err);
  process.exit(1);
});
