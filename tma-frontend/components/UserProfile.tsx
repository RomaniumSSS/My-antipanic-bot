'use client';

import type { User } from '@/lib/api';
import { useTelegram } from '@/app/providers';

interface UserProfileProps {
  user: User;
}

export function UserProfile({ user }: UserProfileProps) {
  const { webApp } = useTelegram();
  const tgUser = webApp?.initDataUnsafe?.user;
  
  const displayName = user.first_name || tgUser?.first_name || 'Пользователь';

  return (
    <div className="flex items-center gap-3">
      {/* Avatar */}
      <div className="w-12 h-12 rounded-full bg-tg-button flex items-center justify-center text-tg-button-text text-lg font-bold">
        {displayName.charAt(0).toUpperCase()}
      </div>
      
      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{displayName}</div>
        {user.username && (
          <div className="text-sm hint-text">@{user.username}</div>
        )}
      </div>
      
      {/* Level badge */}
      <div className="text-right">
        <div className="text-xs hint-text">Уровень</div>
        <div className="text-xl font-bold">{user.level}</div>
      </div>
    </div>
  );
}

export function UserProfileSkeleton() {
  return (
    <div className="flex items-center gap-3">
      <div className="skeleton w-12 h-12 rounded-full" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-5 w-24 rounded" />
        <div className="skeleton h-4 w-16 rounded" />
      </div>
      <div className="skeleton h-8 w-12 rounded" />
    </div>
  );
}
