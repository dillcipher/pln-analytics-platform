type Props = {
  title: string;
};

export default function ComingSoonPage({ title }: Props) {
  return (
    <div>
      <h1>{title}</h1>
      <p>Coming Soon...</p>
    </div>
  );
}